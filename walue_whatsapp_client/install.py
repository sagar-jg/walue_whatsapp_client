"""
Installation hooks for Walue WhatsApp Client

Creates custom fields on CRM Lead doctype
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def after_install():
    """
    Run after app installation

    Creates custom fields on CRM Lead
    """
    create_crm_lead_fields()
    frappe.db.commit()


def create_crm_lead_fields():
    """
    Create custom fields on CRM Lead for WhatsApp integration
    """
    custom_fields = {
        "CRM Lead": [
            {
                "fieldname": "whatsapp_section",
                "fieldtype": "Section Break",
                "label": "WhatsApp",
                "insert_after": "email_id",
                "collapsible": 1,
            },
            {
                "fieldname": "whatsapp_number",
                "fieldtype": "Data",
                "label": "WhatsApp Number",
                "insert_after": "whatsapp_section",
                "description": "Phone number in E.164 format (e.g., +919876543210)",
            },
            {
                "fieldname": "whatsapp_call_permission_status",
                "fieldtype": "Data",
                "label": "Call Permission Status",
                "insert_after": "whatsapp_number",
                "read_only": 1,
            },
            {
                "fieldname": "whatsapp_col_break",
                "fieldtype": "Column Break",
                "insert_after": "whatsapp_call_permission_status",
            },
            {
                "fieldname": "last_whatsapp_call",
                "fieldtype": "Datetime",
                "label": "Last WhatsApp Call",
                "insert_after": "whatsapp_col_break",
                "read_only": 1,
            },
            {
                "fieldname": "last_whatsapp_message",
                "fieldtype": "Datetime",
                "label": "Last WhatsApp Message",
                "insert_after": "last_whatsapp_call",
                "read_only": 1,
            },
            {
                "fieldname": "total_whatsapp_calls",
                "fieldtype": "Int",
                "label": "Total Calls",
                "insert_after": "last_whatsapp_message",
                "read_only": 1,
                "default": "0",
            },
            {
                "fieldname": "total_whatsapp_messages",
                "fieldtype": "Int",
                "label": "Total Messages",
                "insert_after": "total_whatsapp_calls",
                "read_only": 1,
                "default": "0",
            },
        ]
    }

    create_custom_fields(custom_fields)
