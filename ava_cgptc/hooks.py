# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from . import __version__ as app_version

app_name = "ava_cgptc"
app_title = "Ava Cgptc"
app_publisher = "GreyCube Technologies"
app_description = "Customization for customer group"
app_icon = "octicon octicon-beaker"
app_color = "blue"
app_email = "admin@greycube.in"
app_license = "MIT"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/ava_cgptc/css/ava_cgptc.css"
# app_include_js = "/assets/ava_cgptc/js/ava_cgptc.js"

# include js, css files in header of web template
# web_include_css = "/assets/ava_cgptc/css/ava_cgptc.css"
# web_include_js = "/assets/ava_cgptc/js/ava_cgptc.js"

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {"Payment Entry" : "public/js/payment_entry.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }

# Website user home page (by function)
# get_website_user_home_page = "ava_cgptc.utils.get_home_page"

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Installation
# ------------

# before_install = "ava_cgptc.install.before_install"
# after_install = "ava_cgptc.install.after_install"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "ava_cgptc.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
#	}
# }
doc_events = {
	"Sales Order": {
		"on_submit": "ava_cgptc.api.check_customer_group_credit_limit_so"
	},
	"Sales Invoice": {
		"on_submit": "ava_cgptc.api.check_customer_group_credit_limit_si"
	},	
}
# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"ava_cgptc.tasks.all"
# 	],
# 	"daily": [
# 		"ava_cgptc.tasks.daily"
# 	],
# 	"hourly": [
# 		"ava_cgptc.tasks.hourly"
# 	],
# 	"weekly": [
# 		"ava_cgptc.tasks.weekly"
# 	]
# 	"monthly": [
# 		"ava_cgptc.tasks.monthly"
# 	]
# }

# Testing
# -------

# before_tests = "ava_cgptc.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "ava_cgptc.event.get_events"
# }
#
# override_whitelisted_methods = {
	# "erpnext.accounts.doctype.payment_entry.payment_entry.get_party_details": "ava_cgptc.api.get_party_details"
# }
fixtures = ['Party Type']
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "ava_cgptc.task.get_dashboard_data"
# }

