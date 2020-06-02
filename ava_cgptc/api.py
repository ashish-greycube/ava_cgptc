import frappe
from frappe.utils import flt, cint,fmt_money
from frappe import _, msgprint, throw

# SO SI: check_customer_group_credit_limit
def get_customer_group_outstanding(customer,customer_group,company,ignore_outstanding_sales_order=False, cost_center=None):
	# Outstanding based on GL Entries

	cond = ""
	if cost_center:
		lft, rgt = frappe.get_cached_value("Cost Center",
			cost_center, ['lft', 'rgt'])

		cond = """ and cost_center in (select name from `tabCost Center` where
			lft >= {0} and rgt <= {1})""".format(lft, rgt)

	outstanding_based_on_gle_customer_group = frappe.db.sql("""
		select sum(debit) - sum(credit)
		from `tabGL Entry` where party_type = 'Customer Group'
		and party = %s and company=%s {0}""".format(cond), (customer_group, company))

	outstanding_based_on_gle_customer_group = flt(outstanding_based_on_gle_customer_group[0][0]) if outstanding_based_on_gle_customer_group else 0

	# Outstanding based on all customers of customer group
	outstanding_based_on_gle_for_all_customers_in_group=0
	cond = ""
	if cost_center:
		lft, rgt = frappe.get_cached_value("Cost Center",
			cost_center, ['lft', 'rgt'])

		cond = """ and cost_center in (select name from `tabCost Center` where
			lft >= {0} and rgt <= {1})""".format(lft, rgt)

	if (customer_group):
		lft, rgt = frappe.db.get_value("Customer Group", customer_group, ['lft', 'rgt'])
		get_parent_customer_groups=frappe.db.sql("""select name from `tabCustomer Group` where lft >= %s and rgt <= %s""", (lft, rgt), as_dict=1)
		customer_groups = ["%s"%(frappe.db.escape(d.name)) for d in get_parent_customer_groups]
		if customer_groups:
			condition = ""
			customer_group_condition = ",".join(['%s'] * len(customer_groups))%(tuple(customer_groups))
			condition="{0} in ({1})".format(' and customer_group', customer_group_condition)

		customer_list=frappe.db.sql(""" select name from `tabCustomer` where docstatus < 2 {cond} """.format(cond=condition), as_dict=1)
		customer_list = ["%s"%(frappe.db.escape(d.name)) for d in customer_list]
		condition = "1=1"
		if len(customer_list)>0:
			customer_list = ",".join(['%s'] * len(customer_list))%(tuple(customer_list))
			condition="{0} in ({1})".format(' and party', customer_list)
			print('customer_list',condition)
		outstanding_based_on_gle_for_all_customers_in_group = frappe.db.sql("""
			select sum(debit) - sum(credit)
			from `tabGL Entry` where party_type = 'Customer'
			{condition} and company=%s {cond}""".format(condition=condition,cond=cond), (company))
		outstanding_based_on_gle_for_all_customers_in_group = flt(outstanding_based_on_gle_for_all_customers_in_group[0][0]) if outstanding_based_on_gle_for_all_customers_in_group else 0
		print('outstanding_based_on_gle_for_all_customers_in_group',outstanding_based_on_gle_for_all_customers_in_group)
	# Outstanding based on Sales Order
	outstanding_based_on_so_customer_group = 0.0

	# if credit limit check is bypassed at sales order level,
	# we should not consider outstanding Sales Orders, when customer credit balance report is run
	if not ignore_outstanding_sales_order:
		outstanding_based_on_so_customer_group = frappe.db.sql("""
			select sum(base_grand_total*(100 - per_billed)/100)
			from `tabSales Order`
			where customer_group=%s and docstatus = 1 and company=%s
			and per_billed < 100 and status != 'Closed'""", (customer_group, company))
		outstanding_based_on_so_customer_group = flt(outstanding_based_on_so_customer_group[0][0]) if outstanding_based_on_so_customer_group else 0.0

	# Outstanding based on Delivery Note, which are not created against Sales Order
	unmarked_delivery_note_items_customer_group = frappe.db.sql("""select
			dn_item.name, dn_item.amount, dn.base_net_total, dn.base_grand_total
		from `tabDelivery Note` dn, `tabDelivery Note Item` dn_item
		where
			dn.name = dn_item.parent
			and dn.customer_group=%s and dn.company=%s
			and dn.docstatus = 1 and dn.status not in ('Closed', 'Stopped')
			and ifnull(dn_item.against_sales_order, '') = ''
			and ifnull(dn_item.against_sales_invoice, '') = ''
		""", (customer_group, company), as_dict=True)

	outstanding_based_on_dn = 0.0

	for dn_item in unmarked_delivery_note_items_customer_group:
		si_amount = frappe.db.sql("""select sum(amount)
			from `tabSales Invoice Item`
			where dn_detail = %s and docstatus = 1""", dn_item.name)[0][0]

		if flt(dn_item.amount) > flt(si_amount) and dn_item.base_net_total:
			outstanding_based_on_dn += ((flt(dn_item.amount) - flt(si_amount)) \
				/ dn_item.base_net_total) * dn_item.base_grand_total
	print("-"*2000)
	print("outstanding_based_on_gle_customer_group ,outstanding_based_on_gle_for_all_customers_in_group ,outstanding_based_on_so_customer_group , outstanding_based_on_dn")
	print(outstanding_based_on_gle_customer_group ,outstanding_based_on_gle_for_all_customers_in_group ,outstanding_based_on_so_customer_group , outstanding_based_on_dn)
	return outstanding_based_on_gle_customer_group + outstanding_based_on_gle_for_all_customers_in_group + outstanding_based_on_so_customer_group + outstanding_based_on_dn

def get_credit_limit_for_customer_group(customer_group,company):
	credit_limit = frappe.db.get_value("Ava Customer Group Credit Limit",
		{'parent': customer_group, 'parenttype': 'Customer Group', 'company': company}, 'credit_limit')
	print("-"*500)
	print('credit_limit',credit_limit)
	return flt(credit_limit)

def check_credit_limit_for_customer_group(customer,customer_group, company, ignore_outstanding_sales_order=False, extra_amount=0):
		# default_currency = frappe.db.get_default("currency")
		customer_group_outstanding = get_customer_group_outstanding(customer,customer_group,company, ignore_outstanding_sales_order)
		if extra_amount > 0:
			customer_group_outstanding += flt(extra_amount)

		credit_limit = get_credit_limit_for_customer_group(customer_group, company)
		customer_group_outstanding_formatted=flt(customer_group_outstanding)
		credit_limit_formatted=flt(credit_limit)
		if credit_limit > 0 and flt(customer_group_outstanding) > credit_limit:
			msgprint(_("Credit limit has been crossed for customer group {0} ({1}/{2})")
				.format(customer_group,customer_group_outstanding_formatted ,credit_limit_formatted))

			# If not authorized person raise exception
			credit_controller = frappe.db.get_value('Accounts Settings', None, 'credit_controller')
			if not credit_controller or credit_controller not in frappe.get_roles():
				throw(_("Please contact to the user who have Sales Master Manager {0} role")
					.format(" / " + credit_controller if credit_controller else ""))		

def check_customer_group_credit_limit_so(self,method):
	if not cint(frappe.db.get_value("Ava Customer Group Credit Limit",
		{'parent': self.customer_group, 'parenttype': 'Customer Group', 'company': self.company},
		"bypass_credit_limit_check")):
		customer=self.customer
		company=self.company
		extra_amount=0
		ignore_outstanding_sales_order=False
		customer_group=self.customer_group
		check_credit_limit_for_customer_group(customer,customer_group, company, ignore_outstanding_sales_order,extra_amount)


def check_customer_group_credit_limit_si(self,method):
		if not self.is_return:
			validate_against_credit_limit = False
			bypass_credit_limit_check_at_sales_order = frappe.db.get_value("Ava Customer Group Credit Limit",
				filters={'parent': self.customer_group, 'parenttype': 'Customer Group', 'company': self.company},
				fieldname=["bypass_credit_limit_check"])

			if bypass_credit_limit_check_at_sales_order:
				validate_against_credit_limit = True

			for d in self.get("items"):
				if not (d.sales_order or d.delivery_note):
					validate_against_credit_limit = True
					break
			if validate_against_credit_limit:
				check_credit_limit_for_customer_group(self.customer,self.customer_group,self.company, bypass_credit_limit_check_at_sales_order)

# Payment Entry : scrub paty_type

def override_set_missing_values(self,method):
    from erpnext.accounts.doctype.payment_entry.payment_entry import PaymentEntry
    setattr(PaymentEntry, 'set_missing_values', set_missing_values_custom)

def set_missing_values_custom(self):
	from frappe import scrub
	from erpnext.accounts.utils import  get_account_currency, get_balance_on
	from erpnext.accounts.party import get_party_account
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_account_details
	if self.payment_type == "Internal Transfer":
		for field in ("party", "party_balance", "total_allocated_amount",
			"base_total_allocated_amount", "unallocated_amount"):
				self.set(field, None)
		self.references = []
	else:
		if not self.party_type:
			frappe.throw(_("Party Type is mandatory"))

		if not self.party:
			frappe.throw(_("Party is mandatory"))
		_party_name = "title" if self.party_type in ("Student", "Shareholder") else scrub(self.party_type.lower()) + "_name"
		self.party_name = frappe.db.get_value(self.party_type, self.party, _party_name)

	if self.party:
		if not self.party_balance:
			self.party_balance = get_balance_on(party_type=self.party_type,
				party=self.party, date=self.posting_date, company=self.company)

		if not self.party_account:
			party_account = get_party_account(self.party_type, self.party, self.company)
			self.set(self.party_account_field, party_account)
			self.party_account = party_account

	if self.paid_from and not (self.paid_from_account_currency or self.paid_from_account_balance):
		acc = get_account_details(self.paid_from, self.posting_date, self.cost_center)
		self.paid_from_account_currency = acc.account_currency
		self.paid_from_account_balance = acc.account_balance

	if self.paid_to and not (self.paid_to_account_currency or self.paid_to_account_balance):
		acc = get_account_details(self.paid_to, self.posting_date, self.cost_center)
		self.paid_to_account_currency = acc.account_currency
		self.paid_to_account_balance = acc.account_balance

	self.party_account_currency = self.paid_from_account_currency \
		if self.payment_type=="Receive" else self.paid_to_account_currency

	self.set_missing_ref_details()	

@frappe.whitelist()
def get_party_details(company, party_type, party, date, cost_center=None):
	from frappe import scrub
	from erpnext.accounts.party import get_party_account
	from erpnext.accounts.utils import get_account_currency,get_balance_on
	bank_account = ''
	if not frappe.db.exists(party_type, party):
		frappe.throw(_("Invalid {0}: {1}").format(party_type, party))

	party_account = get_party_account(party_type, party, company)

	account_currency = get_account_currency(party_account)
	account_balance = get_balance_on(party_account, date, cost_center=cost_center)
	_party_name = "title" if party_type in ("Student", "Shareholder") else scrub(party_type.lower()) + "_name"
	party_name = frappe.db.get_value(party_type, party, _party_name)
	party_balance = get_balance_on(party_type=party_type, party=party, cost_center=cost_center)
	if party_type in ["Customer", "Supplier"]:
		bank_account = get_party_bank_account(party_type, party)

	return {
		"party_account": party_account,
		"party_name": party_name,
		"party_account_currency": account_currency,
		"party_balance": party_balance,
		"account_balance": account_balance,
		"bank_account": bank_account
	}
# Payment Entry : scrub paty_type