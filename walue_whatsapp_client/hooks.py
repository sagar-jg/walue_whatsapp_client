app_name = "walue_whatsapp_client"
app_title = "Walue WhatsApp Client"
app_publisher = "Walue Biz"
app_description = "WhatsApp Calling & Messaging for Frappe/ERPNext CRM - Integrates with CRM Leads for WhatsApp communication"
app_email = "support@walue.biz"
app_license = "MIT"
app_version = "0.0.1"

# Required Apps
# required_apps = ["erpnext"]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
app_include_css = "/assets/walue_whatsapp_client/css/whatsapp_client.css"
app_include_js = "/assets/walue_whatsapp_client/js/whatsapp_client.js"

# include js, css files in header of web template
# web_include_css = "/assets/walue_whatsapp_client/css/walue_whatsapp_client.css"
# web_include_js = "/assets/walue_whatsapp_client/js/walue_whatsapp_client.js"

# include custom scss in every website theme (without signing in)
# website_theme_scss = "walue_whatsapp_client/public/scss/website"

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
    "CRM Lead": "public/js/crm_lead.js"
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "walue_whatsapp_client/public/icons.svg"

# Home Pages
# ----------
# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#     "Role": "home_page"
# }

# Generators
# ----------
# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Installation
# ------------
# before_install = "walue_whatsapp_client.install.before_install"
after_install = "walue_whatsapp_client.install.after_install"

# Uninstallation
# ------------
# before_uninstall = "walue_whatsapp_client.uninstall.before_uninstall"
# after_uninstall = "walue_whatsapp_client.uninstall.after_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config
# notification_config = "walue_whatsapp_client.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways
# permission_query_conditions = {
#     "Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }

# has_permission = {
#     "Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes
# override_doctype_class = {
#     "ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events
# doc_events = {
#     "*": {
#         "on_update": "method",
#         "on_cancel": "method",
#         "on_trash": "method"
#     }
# }

# Scheduled Tasks
# ---------------
scheduler_events = {
    "all": [
        "walue_whatsapp_client.tasks.poll_message_status"
    ],
    "hourly": [
        "walue_whatsapp_client.tasks.sync_templates",
        "walue_whatsapp_client.tasks.report_usage_to_provider"
    ],
    "daily": [
        "walue_whatsapp_client.tasks.check_permission_expiry"
    ]
}

# Testing
# -------
# before_tests = "walue_whatsapp_client.install.before_tests"

# Overriding Methods
# ------------------------------
# override_whitelisted_methods = {
#     "frappe.desk.doctype.event.event.get_events": "walue_whatsapp_client.event.get_events"
# }

# override_doctype_dashboards = {
#     "Task": "walue_whatsapp_client.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["walue_whatsapp_client.utils.before_request"]
# after_request = ["walue_whatsapp_client.utils.after_request"]

# Job Events
# ----------
# before_job = ["walue_whatsapp_client.utils.before_job"]
# after_job = ["walue_whatsapp_client.utils.after_job"]

# User Data Protection
# --------------------
# user_data_fields = [
#     {
#         "doctype": "{doctype_1}",
#         "filter_by": "{filter_by}",
#         "redact_fields": ["{field_1}", "{field_2}"],
#         "partial": 1,
#     },
# ]

# Authentication and authorization
# --------------------------------
# auth_hooks = [
#     "walue_whatsapp_client.auth.validate"
# ]

# Automatically update python dependencies
# -----------------------------------------
# required_apps = []

# Translation
# --------------------------------
# Make link fields searchable in specific doctypes
# links_field_to_search_doctypes = ["Asset", "Task"]

# Fixtures - export custom fields added to CRM Lead
fixtures = [
    {
        "dt": "Custom Field",
        "filters": [
            ["dt", "=", "CRM Lead"],
            ["fieldname", "in", [
                "whatsapp_number",
                "whatsapp_call_permission_status",
                "last_whatsapp_call",
                "last_whatsapp_message",
                "total_whatsapp_calls",
                "total_whatsapp_messages"
            ]]
        ]
    }
]
