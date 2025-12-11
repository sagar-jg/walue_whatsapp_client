"""
Setup API for Initial Configuration

This module handles:
1. Embedded signup initiation
2. Manual WABA configuration
3. Template sync
"""

import frappe
from frappe import _
import requests

from walue_whatsapp_client.constants import ERR_NOT_CONFIGURED, ERR_PROVIDER_ERROR
from walue_whatsapp_client.api.auth import get_provider_headers


@frappe.whitelist()
def initiate_signup() -> dict:
    """
    Initiate embedded signup flow

    Starts the Meta embedded signup process via provider

    Returns:
        dict: Contains signup_url to redirect user
    """
    settings = frappe.get_single("WhatsApp Settings")

    if not settings.provider_url or not settings.provider_access_token:
        frappe.throw(_(ERR_NOT_CONFIGURED))

    try:
        # Get customer ID from provider (registered during initial setup)
        response = requests.get(
            f"{settings.provider_url}/api/method/walue_whatsapp_provider.api.customers.get_info",
            headers=get_provider_headers()
        )

        if response.status_code != 200:
            return {"success": False, "error": ERR_PROVIDER_ERROR}

        customer_info = response.json()
        customer_id = customer_info.get("customer_id")

        if not customer_id:
            return {"success": False, "error": "Not registered with provider"}

        # Initiate embedded signup
        signup_response = requests.post(
            f"{settings.provider_url}/api/method/walue_whatsapp_provider.api.embedded_signup.initiate",
            headers=get_provider_headers(),
            json={"customer_id": customer_id}
        )

        result = signup_response.json()

        if result.get("success"):
            return {
                "success": True,
                "signup_url": result.get("signup_url"),
                "session_id": result.get("session_id"),
            }
        else:
            return {"success": False, "error": result.get("error", ERR_PROVIDER_ERROR)}

    except requests.RequestException as e:
        frappe.log_error(f"Signup initiation failed: {str(e)}")
        return {"success": False, "error": ERR_PROVIDER_ERROR}


@frappe.whitelist()
def complete_signup(waba_credentials: dict) -> dict:
    """
    Complete signup by storing WABA credentials locally

    Called after embedded signup callback

    Args:
        waba_credentials: Dict containing waba_id, phone_number_id, access_token, etc.

    Returns:
        dict: Setup completion status
    """
    settings = frappe.get_single("WhatsApp Settings")

    # Store credentials locally
    settings.meta_waba_id = waba_credentials.get("waba_id")
    settings.meta_phone_number_id = waba_credentials.get("phone_number_id")
    settings.meta_phone_number = waba_credentials.get("phone_number")
    settings.meta_business_id = waba_credentials.get("business_id")
    settings.meta_access_token = waba_credentials.get("access_token")
    settings.save(ignore_permissions=True)

    # Sync templates
    sync_templates()

    return {
        "success": True,
        "message": "WhatsApp Business Account configured successfully",
    }


@frappe.whitelist()
def configure_manual_waba(waba_id: str, phone_number_id: str, phone_number: str,
                          access_token: str, business_id: str = None) -> dict:
    """
    Manually configure existing WABA

    For customers who already have a WhatsApp Business Account

    Args:
        waba_id: WhatsApp Business Account ID
        phone_number_id: Phone number ID
        phone_number: Display phone number
        access_token: Meta API access token
        business_id: Meta Business ID (optional)

    Returns:
        dict: Configuration status
    """
    # Validate credentials by making a test API call
    test_url = f"https://graph.facebook.com/v21.0/{waba_id}"
    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        response = requests.get(test_url, headers=headers)
        if response.status_code != 200:
            return {
                "success": False,
                "error": "Invalid WABA credentials. Please verify your access token.",
            }
    except requests.RequestException:
        return {"success": False, "error": "Could not validate credentials"}

    # Store credentials locally
    settings = frappe.get_single("WhatsApp Settings")
    settings.meta_waba_id = waba_id
    settings.meta_phone_number_id = phone_number_id
    settings.meta_phone_number = phone_number
    settings.meta_business_id = business_id or ""
    settings.meta_access_token = access_token
    settings.save(ignore_permissions=True)

    # Sync templates
    sync_templates()

    return {
        "success": True,
        "message": "WhatsApp Business Account configured successfully",
    }


@frappe.whitelist()
def sync_templates() -> dict:
    """
    Sync message templates from WABA

    Fetches approved templates and stores them locally

    Returns:
        dict: Sync status with template count
    """
    settings = frappe.get_single("WhatsApp Settings")

    if not settings.meta_waba_id or not settings.meta_access_token:
        return {"success": False, "error": "WABA not configured"}

    try:
        # Fetch templates from Meta API
        url = f"https://graph.facebook.com/v21.0/{settings.meta_waba_id}/message_templates"
        headers = {"Authorization": f"Bearer {settings.get_password('meta_access_token')}"}

        response = requests.get(url, headers=headers)

        if response.status_code != 200:
            return {"success": False, "error": "Failed to fetch templates"}

        data = response.json()
        templates = data.get("data", [])

        synced_count = 0
        for template in templates:
            _upsert_template(template)
            synced_count += 1

        settings.last_sync = frappe.utils.now()
        settings.save(ignore_permissions=True)

        return {
            "success": True,
            "message": f"Synced {synced_count} templates",
            "count": synced_count,
        }

    except requests.RequestException as e:
        frappe.log_error(f"Template sync failed: {str(e)}")
        return {"success": False, "error": str(e)}


def _upsert_template(template_data: dict):
    """Create or update a template record"""
    template_name = template_data.get("name")

    existing = frappe.db.get_value("WhatsApp Template", {"template_name": template_name}, "name")

    if existing:
        doc = frappe.get_doc("WhatsApp Template", existing)
    else:
        doc = frappe.get_doc({
            "doctype": "WhatsApp Template",
            "template_name": template_name,
        })

    doc.category = template_data.get("category", "").lower()
    doc.language = template_data.get("language")
    doc.status = template_data.get("status", "").lower()
    doc.components = frappe.as_json(template_data.get("components", []))
    doc.last_synced = frappe.utils.now()

    doc.save(ignore_permissions=True)


@frappe.whitelist()
def check_setup_status() -> dict:
    """
    Check current setup status

    Returns:
        dict: Setup status for each step
    """
    settings = frappe.get_single("WhatsApp Settings")

    return {
        "provider_configured": bool(settings.provider_url),
        "provider_connected": bool(settings.provider_access_token),
        "waba_configured": bool(settings.meta_waba_id and settings.meta_phone_number_id),
        "templates_synced": bool(frappe.db.count("WhatsApp Template")),
        "calling_enabled": settings.calling_enabled,
        "messaging_enabled": settings.messaging_enabled,
    }
