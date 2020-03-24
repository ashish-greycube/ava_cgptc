import frappe
# Payment Entry : scrub paty_type

def override_set_missing_values(self,method):
    from erpnext.accounts.doctype.payment_entry.payment_entry import PaymentEntry
    setattr(PaymentEntry, 'set_missing_values', set_missing_values_custom)

def set_missing_values_custom(self):
	print('--------------')
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