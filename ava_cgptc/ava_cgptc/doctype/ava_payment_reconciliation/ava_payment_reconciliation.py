# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, erpnext
from frappe.utils import flt, today , cstr
from frappe import msgprint, _
from frappe.model.document import Document
from erpnext.accounts.utils import get_outstanding_invoices

class AvaPaymentReconciliation(Document):
	def get_unreconciled_entries(self):
		self.get_nonreconciled_payment_entries()
		self.get_invoice_entries()

	def get_nonreconciled_payment_entries(self):
		self.check_mandatory_to_fetch()

		payment_entries = self.get_payment_entries()
		journal_entries = self.get_jv_entries()

		dr_or_cr_notes = []
		self.add_payment_entries(payment_entries + journal_entries + dr_or_cr_notes)

	def get_payment_entries(self):
		order_doctype = "Sales Order" if self.party_type in ["Customer Group","Customer"] else "Purchase Order"
		payment_entries = get_advance_payment_entries(self.party_type, self.party,
			self.receivable_payable_account, order_doctype, against_all_orders=True, limit=self.limit)

		return payment_entries

	def get_jv_entries(self):
		dr_or_cr = ("credit_in_account_currency" if erpnext.get_party_account_type(self.party_type) == 'Receivable'
			else "debit_in_account_currency")

		bank_account_condition = "t2.against_account like %(bank_cash_account)s" \
				if self.bank_cash_account else "1=1"

		limit_cond = "limit %s" % self.limit if self.limit else ""

		journal_entries = frappe.db.sql("""
			select
				"Journal Entry" as reference_type, t1.name as reference_name,
				t1.posting_date, t1.remark as remarks, t2.name as reference_row,
				{dr_or_cr} as amount, t2.is_advance
			from
				`tabJournal Entry` t1, `tabJournal Entry Account` t2
			where
				t1.name = t2.parent and t1.docstatus = 1 and t2.docstatus = 1
				and t2.party_type = %(party_type)s and t2.party = %(party)s
				and t2.account = %(account)s and {dr_or_cr} > 0
				and (t2.reference_type is null or t2.reference_type = '' or
					(t2.reference_type in ('Sales Order', 'Purchase Order')
						and t2.reference_name is not null and t2.reference_name != ''))
				and (CASE
					WHEN t1.voucher_type in ('Debit Note', 'Credit Note')
					THEN 1=1
					ELSE {bank_account_condition}
				END)
			order by t1.posting_date {limit_cond}
			""".format(**{
				"dr_or_cr": dr_or_cr,
				"bank_account_condition": bank_account_condition,
				"limit_cond": limit_cond
			}), {
				"party_type": self.party_type,
				"party": self.party,
				"account": self.receivable_payable_account,
				"bank_cash_account": "%%%s%%" % self.bank_cash_account
			}, as_dict=1)

		return list(journal_entries)

	def add_payment_entries(self, entries):
		self.set('payments', [])
		for e in entries:
			row = self.append('payments', {})
			row.update(e)

	def get_invoice_entries(self):
		#Fetch JVs, Sales and Purchase Invoices for 'invoices' to reconcile against

		condition = self.check_condition()
		non_reconciled_invoices=[]

		if self.party_type=='Customer Group' and self.party:
			lft, rgt = frappe.db.get_value("Customer Group", self.party, ['lft', 'rgt'])
			get_parent_customer_groups=frappe.db.sql("""select name from `tabCustomer Group` where lft >= %s and rgt <= %s""", (lft, rgt), as_dict=1)
			customer_groups = ["%s"%(frappe.db.escape(d.name)) for d in get_parent_customer_groups]
			if customer_groups:
				cond = "and 1=1"
				customer_group_condition = ",".join(['%s'] * len(customer_groups))%(tuple(customer_groups))
				condition_customer="{0} in ({1})".format(' and customer_group', customer_group_condition)
				cond+=condition_customer

			customer_list=frappe.db.sql(""" select name from `tabCustomer` where docstatus < 2 {cond} """.format(cond=cond), as_list=1)
			if len(customer_list)>0:
				# frappe._dict({'party': customer[0]})
				for customer in customer_list:
					outstanding_invoices=get_outstanding_invoices("Customer", customer,
						self.receivable_payable_account, condition=condition)
					for invoice in outstanding_invoices:
						invoice.update({"party":customer[0]})
					non_reconciled_invoices+=outstanding_invoices

				if self.limit:
					non_reconciled_invoices = non_reconciled_invoices[:self.limit]
				self.add_invoice_entries(non_reconciled_invoices)

	def add_invoice_entries(self, non_reconciled_invoices):
		#Populate 'invoices' with JVs and Invoices to reconcile against
		self.set('invoices', [])

		for e in non_reconciled_invoices:
			ent = self.append('invoices', {})
			ent.invoice_type = e.get('voucher_type')
			ent.invoice_number = e.get('voucher_no')
			ent.invoice_date = e.get('posting_date')
			ent.amount = flt(e.get('invoice_amount'))
			ent.outstanding_amount = e.get('outstanding_amount')
			ent.party=e.get('party')

	def reconcile(self, args):
		for e in self.get('payments'):
			e.invoice_type = None
			if e.invoice_number and " | " in e.invoice_number:
				e.invoice_type, e.invoice_number = e.invoice_number.split(" | ")

		self.get_invoice_entries()
		self.validate_invoice()
		dr_or_cr = ("credit_in_account_currency"
			if erpnext.get_party_account_type(self.party_type) == 'Receivable' else "debit_in_account_currency")

		lst = []
		dr_or_cr_notes = []
		for e in self.get('payments'):
			reconciled_entry = []
			if e.invoice_number and e.allocated_amount:
				if e.reference_type in ['Sales Invoice', 'Purchase Invoice']:
					reconciled_entry = dr_or_cr_notes
				else:
					reconciled_entry = lst

				reconciled_entry.append(self.get_payment_details(e, dr_or_cr))

		if lst:
			reconcile_against_document(lst)

		if dr_or_cr_notes:
			reconcile_dr_cr_note(dr_or_cr_notes)

		msgprint(_("Successfully Reconciled"))
		self.get_unreconciled_entries()

	def get_payment_details(self, row, dr_or_cr):
		print('get_payment_details',row.reference_name, '--',row.party,'row.party')
		return frappe._dict({
			'voucher_type': row.reference_type,
			'voucher_no' : row.reference_name,
			'voucher_detail_no' : row.reference_row,
			'against_voucher_type' : row.invoice_type,
			'against_voucher'  : row.invoice_number,
			'account' : self.receivable_payable_account,
			'party_type': self.party_type,
			'party': self.party,
			'party_customer':row.party,
			'is_advance' : row.is_advance,
			'dr_or_cr' : dr_or_cr,
			'unadjusted_amount' : flt(row.amount),
			'allocated_amount' : flt(row.allocated_amount),
			'difference_amount': row.difference_amount,
			'difference_account': row.difference_account
		})

	def get_difference_amount(self, child_row):
		if child_row.get("reference_type") != 'Ava Payment Entry': return

		child_row = frappe._dict(child_row)

		if child_row.invoice_number and " | " in child_row.invoice_number:
			child_row.invoice_type, child_row.invoice_number = child_row.invoice_number.split(" | ")

		dr_or_cr = ("credit_in_account_currency"
			if erpnext.get_party_account_type(self.party_type) == 'Receivable' else "debit_in_account_currency")

		row = self.get_payment_details(child_row, dr_or_cr)

		
		doc = frappe.get_doc(row.voucher_type, row.voucher_no)
		
		update_reference_in_payment_entry(row, doc, do_not_save=True)

		return doc.difference_amount

	def check_mandatory_to_fetch(self):
		for fieldname in ["company", "party_type", "party", "receivable_payable_account"]:
			if not self.get(fieldname):
				frappe.throw(_("Please select {0} first").format(self.meta.get_label(fieldname)))

	def validate_invoice(self):
		if not self.get("invoices"):
			frappe.throw(_("No records found in the Invoice table"))

		if not self.get("payments"):
			frappe.throw(_("No records found in the Payment table"))

		unreconciled_invoices = frappe._dict()
		for d in self.get("invoices"):
			unreconciled_invoices.setdefault(d.invoice_type, {}).setdefault(d.invoice_number, d.outstanding_amount)

		invoices_to_reconcile = []
		for p in self.get("payments"):
			if p.invoice_type and p.invoice_number and p.allocated_amount:
				invoices_to_reconcile.append(p.invoice_number)

				if p.invoice_number not in unreconciled_invoices.get(p.invoice_type, {}):
					frappe.throw(_("{0}: {1} not found in Invoice Details table")
						.format(p.invoice_type, p.invoice_number))

				if flt(p.allocated_amount) > flt(p.amount):
					frappe.throw(_("Row {0}: Allocated amount {1} must be less than or equals to Ava Payment Entry amount {2}")
						.format(p.idx, p.allocated_amount, p.amount))

				invoice_outstanding = unreconciled_invoices.get(p.invoice_type, {}).get(p.invoice_number)
				if flt(p.allocated_amount) - invoice_outstanding > 0.009:
					frappe.throw(_("Row {0}: Allocated amount {1} must be less than or equals to invoice outstanding amount {2}")
						.format(p.idx, p.allocated_amount, invoice_outstanding))

		if not invoices_to_reconcile:
			frappe.throw(_("Please select Allocated Amount, Invoice Type and Invoice Number in atleast one row"))

	def check_condition(self):
		cond = " and posting_date >= {0}".format(frappe.db.escape(self.from_date)) if self.from_date else ""
		cond += " and posting_date <= {0}".format(frappe.db.escape(self.to_date)) if self.to_date else ""
		dr_or_cr = ("debit_in_account_currency" if erpnext.get_party_account_type(self.party_type) == 'Receivable'
			else "credit_in_account_currency")

		if self.minimum_amount:
			cond += " and `{0}` >= {1}".format(dr_or_cr, flt(self.minimum_amount))
		if self.maximum_amount:
			cond += " and `{0}` <= {1}".format(dr_or_cr, flt(self.maximum_amount))

		return cond

def reconcile_dr_cr_note(dr_cr_notes):
	for d in dr_cr_notes:
		voucher_type = ('Credit Note'
			if d.voucher_type == 'Sales Invoice' else 'Debit Note')

		reconcile_dr_or_cr = ('debit_in_account_currency'
			if d.dr_or_cr == 'credit_in_account_currency' else 'credit_in_account_currency')

		jv = frappe.get_doc({
			"doctype": "Journal Entry",
			"voucher_type": voucher_type,
			"posting_date": today(),
			"accounts": [
				{
					'account': d.account,
					'party': d.party,
					'party_type': d.party_type,
					d.dr_or_cr: abs(d.allocated_amount),
					'reference_type': d.against_voucher_type,
					'reference_name': d.against_voucher
				},
				{
					'account': d.account,
					'party': d.party,
					'party_type': d.party_type,
					reconcile_dr_or_cr: (abs(d.allocated_amount)
						if abs(d.unadjusted_amount) > abs(d.allocated_amount) else abs(d.unadjusted_amount)),
					'reference_type': d.voucher_type,
					'reference_name': d.voucher_no
				}
			]
		})

		jv.submit()

def get_advance_payment_entries(party_type, party, party_account, order_doctype,
		order_list=None, include_unallocated=True, against_all_orders=False, limit=None):
	party_account_field = "paid_from" if party_type in["Customer","Customer Group"] else "paid_to"
	payment_type = "Receive" if party_type in["Customer","Customer Group"]  else "Pay"
	payment_entries_against_order, unallocated_payment_entries = [], []
	limit_cond = "limit %s" % limit if limit else ""

	if order_list or against_all_orders:
		if order_list:
			reference_condition = " and t2.reference_name in ({0})" \
				.format(', '.join(['%s'] * len(order_list)))
		else:
			reference_condition = ""
			order_list = []

		payment_entries_against_order = frappe.db.sql("""
			select
				"Ava Payment Entry" as reference_type, t1.name as reference_name,
				t1.remarks, t2.allocated_amount as amount, t2.name as reference_row,
				t2.reference_name as against_order, t1.posting_date
			from `tabAva Payment Entry` t1, `tabAva Payment Entry Reference` t2
			where
				t1.name = t2.parent and t1.{0} = %s and t1.payment_type = %s
				and t1.party_type = %s and t1.party = %s and t1.docstatus = 1
				and t2.reference_doctype = %s {1}
			order by t1.posting_date {2}
		""".format(party_account_field, reference_condition, limit_cond),
													  [party_account, payment_type, party_type, party,
													   order_doctype] + order_list, as_dict=1)

	if include_unallocated:
		unallocated_payment_entries = frappe.db.sql("""
				select "Ava Payment Entry" as reference_type, name as reference_name,
				remarks, unallocated_amount as amount
				from `tabAva Payment Entry`
				where
					{0} = %s and party_type = %s and party = %s and payment_type = %s
					and docstatus = 1 and unallocated_amount > 0
				order by posting_date {1}
			""".format(party_account_field, limit_cond), (party_account, party_type, party, payment_type), as_dict=1)
	return list(payment_entries_against_order) + list(unallocated_payment_entries)


def reconcile_against_document(args):
	"""
		Cancel JV, Update aginst document, split if required and resubmit jv
	"""
	for d in args:

		check_if_advance_entry_modified(d)
		validate_allocated_amount(d)

		# cancel advance entry
		doc = frappe.get_doc(d.voucher_type, d.voucher_no)

		doc.make_gl_entries(cancel=1, adv_adj=1)

		# update ref in advance entry
		if d.voucher_type == "Journal Entry":
			update_reference_in_journal_entry(d, doc)
		else:
			update_reference_in_payment_entry(d, doc)

		# re-submit advance entry
		doc = frappe.get_doc(d.voucher_type, d.voucher_no)
		doc.make_gl_entries(cancel = 0, adv_adj =1)
		if d.voucher_type in ('Ava Payment Entry', 'Journal Entry'):
			doc.update_expense_claim()

def check_if_advance_entry_modified(args):
	"""
		check if there is already a voucher reference
		check if amount is same
		check if jv is submitted
	"""
	ret = None
	if args.voucher_type == "Journal Entry":
		ret = frappe.db.sql("""
			select t2.{dr_or_cr} from `tabJournal Entry` t1, `tabJournal Entry Account` t2
			where t1.name = t2.parent and t2.account = %(account)s
			and t2.party_type = %(party_type)s and t2.party = %(party)s
			and (t2.reference_type is null or t2.reference_type in ("", "Sales Order", "Purchase Order"))
			and t1.name = %(voucher_no)s and t2.name = %(voucher_detail_no)s
			and t1.docstatus=1 """.format(dr_or_cr = args.get("dr_or_cr")), args)
	else:
		party_account_field = ("paid_from"
			if erpnext.get_party_account_type(args.party_type) == 'Receivable' else "paid_to")

		if args.voucher_detail_no:
			ret = frappe.db.sql("""select t1.name
				from `tabAva Payment Entry` t1, `tabAva Payment Entry Reference` t2
				where
					t1.name = t2.parent and t1.docstatus = 1
					and t1.name = %(voucher_no)s and t2.name = %(voucher_detail_no)s
					and t1.party_type = %(party_type)s and t1.party = %(party)s and t1.{0} = %(account)s
					and t2.reference_doctype in ("", "Sales Order", "Purchase Order")
					and t2.allocated_amount = %(unadjusted_amount)s
			""".format(party_account_field), args)
		else:
			ret = frappe.db.sql("""select name from `tabAva Payment Entry`
				where
					name = %(voucher_no)s and docstatus = 1
					and party_type = %(party_type)s and party = %(party)s and {0} = %(account)s
					and unallocated_amount = %(unadjusted_amount)s
			""".format(party_account_field), args)

	if not ret:
		throw(_("""Ava Payment Entry has been modified after you pulled it. Please pull it again."""))

def validate_allocated_amount(args):
	if args.get("allocated_amount") < 0:
		throw(_("Allocated amount cannot be negative"))
	elif args.get("allocated_amount") > args.get("unadjusted_amount"):
		throw(_("Allocated amount cannot be greater than unadjusted amount"))	


def update_reference_in_journal_entry(d, jv_obj):
	"""
		Updates against document, if partial amount splits into rows
	"""
	jv_detail = jv_obj.get("accounts", {"name": d["voucher_detail_no"]})[0]
	jv_detail.set(d["dr_or_cr"], d["allocated_amount"])
	jv_detail.set('debit' if d['dr_or_cr']=='debit_in_account_currency' else 'credit',
		d["allocated_amount"]*flt(jv_detail.exchange_rate))
	jv_detail.set("party_type","Customer" )
	jv_detail.set("party",frappe.get_value(d["against_voucher_type"], d["against_voucher"], "customer") )
	original_reference_type = jv_detail.reference_type
	original_reference_name = jv_detail.reference_name

	jv_detail.set("reference_type", d["against_voucher_type"])
	jv_detail.set("reference_name", d["against_voucher"])

	if d['allocated_amount'] < d['unadjusted_amount']:
		jvd = frappe.db.sql("""
			select cost_center, balance, against_account, is_advance,
				account_type, exchange_rate, account_currency
			from `tabJournal Entry Account` where name = %s
		""", d['voucher_detail_no'], as_dict=True)

		amount_in_account_currency = flt(d['unadjusted_amount']) - flt(d['allocated_amount'])
		amount_in_company_currency = amount_in_account_currency * flt(jvd[0]['exchange_rate'])

		# new entry with balance amount
		ch = jv_obj.append("accounts")
		ch.account = d['account']
		ch.account_type = jvd[0]['account_type']
		ch.account_currency = jvd[0]['account_currency']
		ch.exchange_rate = jvd[0]['exchange_rate']
		ch.party_type = d["party_type"] 
		ch.party =  d["party"]
		ch.cost_center = cstr(jvd[0]["cost_center"])
		ch.balance = flt(jvd[0]["balance"])

		ch.set(d['dr_or_cr'], amount_in_account_currency)
		ch.set('debit' if d['dr_or_cr']=='debit_in_account_currency' else 'credit', amount_in_company_currency)

		ch.set('credit_in_account_currency' if d['dr_or_cr']== 'debit_in_account_currency'
			else 'debit_in_account_currency', 0)
		ch.set('credit' if d['dr_or_cr']== 'debit_in_account_currency' else 'debit', 0)

		ch.against_account = cstr(jvd[0]["against_account"])
		ch.reference_type = original_reference_type
		ch.reference_name = original_reference_name
		ch.is_advance = cstr(jvd[0]["is_advance"])
		ch.docstatus = 1

	# will work as update after submit
	jv_obj.flags.ignore_validate_update_after_submit = True
	jv_obj.save(ignore_permissions=True)

def update_reference_in_payment_entry(d, payment_entry, do_not_save=False):
	reference_details = {
		"reference_doctype": d.against_voucher_type,
		"reference_name": d.against_voucher,
		"party":d.party_customer,
		"total_amount": d.grand_total,
		"outstanding_amount": d.outstanding_amount,
		"allocated_amount": d.allocated_amount,
		"exchange_rate": d.exchange_rate
	}

	if d.voucher_detail_no:
		existing_row = payment_entry.get("references", {"name": d["voucher_detail_no"]})[0]
		original_row = existing_row.as_dict().copy()
		existing_row.update(reference_details)

		if d.allocated_amount < original_row.allocated_amount:
			new_row = payment_entry.append("references")
			new_row.docstatus = 1
			for field in list(reference_details):
				new_row.set(field, original_row[field])

			new_row.allocated_amount = original_row.allocated_amount - d.allocated_amount
	else:
		new_row = payment_entry.append("references")
		new_row.docstatus = 1
		new_row.update(reference_details)

	payment_entry.flags.ignore_validate_update_after_submit = True
	payment_entry.setup_party_account_field()
	payment_entry.set_missing_values()
	payment_entry.set_amounts()

	if d.difference_amount and d.difference_account:
		payment_entry.set_gain_or_loss(account_details={
			'account': d.difference_account,
			'cost_center': payment_entry.cost_center or frappe.get_cached_value('Company',
				payment_entry.company, "cost_center"),
			'amount': d.difference_amount
		})

	if not do_not_save:
		payment_entry.save(ignore_permissions=True)
		print('cccccccccccccccccccccccccccccc=======================================================================================')
		for x in payment_entry.get("references"):
			if do_not_save==True:
				print('called from change of invoice dropdoewn')
			else:
				print('called from reconcile',payment_entry.name)
			print(x.name)
			print(x.reference_name)
			print(x.party)
			print(x.reference_doctype)
			print(x.total_amount)
			print(x.allocated_amount)
		print('payment_entry',payment_entry.name)
		print('ppppppppppppppppppp=======================================================================================')		