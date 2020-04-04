from __future__ import unicode_literals
from frappe import _
import frappe


def get_data():
	config = [
		{
			"label": _("Ava Report"),
			"items": [
				{
					"type": "report",
					"name": "Ava General Ledger",
					"is_query_report": True,
					"doctype": "GL Entry"
				}
			]
		},
		{
			"label": _("Ava Accounts"),
			"items": [
				{
					"type": "doctype",
					"name": "Ava Payment Entry",
					"description": _("Payment Entry for Customer Group.")
				},
				{
					"type": "doctype",
					"label": _("Match Payments with Invoices for Customer Group"),
					"name": "Ava Payment Reconciliation",
					"description": _("Match non-linked Invoices and Payments.")
				}				
			]
		}		
		]
	return config