from . import __version__ as app_version

app_name = "qp_supplier_front"
app_title = "Qp Supplier Front"
app_publisher = "Rafael Licett"
app_description = "Front Supplier"
app_icon = "octicon octicon-file-directory"
app_color = "grey"
app_email = "Rafael.licettt@mentum.group"
app_license = "MIT"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/qp_supplier_front/css/qp_supplier_front.css"
# app_include_js = "/assets/qp_supplier_front/js/qp_supplier_front.js"

# include js, css files in header of web template

web_include_css = "/assets/qp_supplier_front/css/qp_supplier_front.css"
web_include_js = ["/assets/qp_supplier_front/js/qp_supplier_front.js", "/assets/qp_supplier_front/js/api_connection.js"]

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "qp_supplier_front/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
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

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Installation
# ------------

# before_install = "qp_supplier_front.install.before_install"
# after_install = "qp_supplier_front.install.after_install"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "qp_supplier_front.notifications.get_notification_config"

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

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
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


#doc_events = {
# 	"Supplier": {
# 		"before_save": "qp_supplier_front.uses_cases.information.complete.handler",
#	}
#}



get_website_user_home_page = "qp_supplier_front.redirect.login.get_home_page"

# Scheduled Tasks
# ---------------

scheduler_events = {
 	"cron": {
		"0 12 * * *": [
			"qp_supplier_front.taks.sync.all"
		]
    },
 	"daily": [
    	"qp_supplier_front.uses_cases.information.tasks.daily"
 		#"qp_supplier_front.tasks.daily"
 	]
# 	"hourly": [
# 		"qp_supplier_front.tasks.hourly"
# 	],
# 	"weekly": [
# 		"qp_supplier_front.tasks.weekly"
# 	]
# 	"monthly": [
# 		"qp_supplier_front.tasks.monthly"
# 	]
}

# Testing
# -------

# before_tests = "qp_supplier_front.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "qp_supplier_front.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "qp_supplier_front.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]


# User Data Protection
# --------------------

#user_data_fields = [
#	{
#		"doctype": "{doctype_1}",
#		"filter_by": "{filter_by}",
#		"redact_fields": ["{field_1}", "{field_2}"],
#		"partial": 1,
#	},
#	{
#		"doctype": "{doctype_2}",
#		"filter_by": "{filter_by}",
#		"partial": 1,
#	},
#	{
#		"doctype": "{doctype_3}",
#		"strict": False,
#	},
#	{
#		"doctype": "{doctype_4}"
#	}
#]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"qp_supplier_front.auth.validate"
# ]

# Fixtures
fixtures = [
    {
        "dt": "Custom Field",
        "filters": [["name", "in", [
            "Supplier-qp_request_edit",
            "Supplier-qp_is_foreigner_supplier",
            "Bank-qp_aba_number",
            "Bank-qp_swift_number",
            "Bank Account-qp_iban_number",
            "Bank Account-qp_routing_code",
            "Contact-qp_contact_type",
            "Supplier-qp_resolution_self_retaining"
        ]]]
    }
]

