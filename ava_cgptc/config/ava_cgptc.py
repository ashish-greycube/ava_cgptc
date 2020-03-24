from __future__ import unicode_literals
from frappe import _
import frappe


def get_data():
	config = [
		{
			"label": _("Report"),
			"items": [
				{
					"type": "report",
					"name": "Ava General Ledger",
					"is_query_report": True,
					"doctype": "GL Entry"
				}
			]
		}]
	return config