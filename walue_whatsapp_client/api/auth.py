"""
Authentication API for Provider Connection

This module handles OAuth connection to Walue Biz provider platform.
Tokens are stored locally in WhatsApp Settings.
"""

import frappe
from frappe import _
import requests
import secrets
from urllib.parse import urlencode

from walue_whatsapp_client.constants import ERR_NOT_CONFIGURED, ERR_PROVIDER_ERROR


@frappe.whitelist()
def connect():
    """
    Initiate OAuth connection with provider

    Generates state token and redirects to provider's OAuth endpoint

    Returns:
        dict: Contains authorization URL
    """
    settings = frappe.get_single("WhatsApp Settings")

    if not settings.provider_url or not settings.provider_oauth_client_id:
        frappe.throw(_(ERR_NOT_CONFIGURED))

    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    frappe.cache().set_value(f"oauth_state:{state}", {"user": frappe.session.user}, expires_in_sec=600)

    # Build callback URL
    callback_url = frappe.utils.get_url("/api/method/walue_whatsapp_client.api.auth.callback")

    # Build authorization URL
    params = {
        "client_id": settings.provider_oauth_client_id,
        "redirect_uri": callback_url,
        "response_type": "code",
        "state": state,
    }

    auth_url = f"{settings.provider_url}/api/method/walue_whatsapp_provider.api.oauth.authorize?{urlencode(params)}"

    return {
        "success": True,
        "authorization_url": auth_url,
    }


@frappe.whitelist(allow_guest=True)
def callback():
    """
    Handle OAuth callback from provider

    Exchanges authorization code for tokens and stores them locally
    """
    code = frappe.form_dict.get("code")
    state = frappe.form_dict.get("state")
    error = frappe.form_dict.get("error")

    if error:
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = "/app/whatsapp-settings?error=" + error
        return

    if not code or not state:
        frappe.throw(_("Missing required parameters"))

    # Validate state
    state_data = frappe.cache().get_value(f"oauth_state:{state}")
    if not state_data:
        frappe.throw(_("Invalid or expired state"))

    frappe.cache().delete_value(f"oauth_state:{state}")

    # Exchange code for tokens
    settings = frappe.get_single("WhatsApp Settings")

    callback_url = frappe.utils.get_url("/api/method/walue_whatsapp_client.api.auth.callback")

    try:
        response = requests.post(
            f"{settings.provider_url}/api/method/walue_whatsapp_provider.api.oauth.token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": callback_url,
                "client_id": settings.provider_oauth_client_id,
                "client_secret": settings.get_password("provider_oauth_client_secret"),
            }
        )

        if response.status_code != 200:
            frappe.log_error(f"OAuth token exchange failed: {response.text}")
            frappe.local.response["type"] = "redirect"
            frappe.local.response["location"] = "/app/whatsapp-settings?error=token_exchange_failed"
            return

        token_data = response.json()

        # Store tokens
        settings.provider_access_token = token_data.get("access_token")
        settings.provider_refresh_token = token_data.get("refresh_token")
        settings.save(ignore_permissions=True)

        frappe.db.commit()

        # Redirect to settings page with success
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = "/app/whatsapp-settings?connected=1"

    except requests.RequestException as e:
        frappe.log_error(f"OAuth callback failed: {str(e)}")
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = "/app/whatsapp-settings?error=connection_failed"


@frappe.whitelist()
def refresh_token():
    """
    Refresh the access token using refresh token

    Returns:
        dict: New access token info
    """
    settings = frappe.get_single("WhatsApp Settings")

    if not settings.provider_refresh_token:
        return {"success": False, "error": "No refresh token available"}

    try:
        response = requests.post(
            f"{settings.provider_url}/api/method/walue_whatsapp_provider.api.oauth.refresh",
            data={
                "refresh_token": settings.get_password("provider_refresh_token"),
                "client_id": settings.provider_oauth_client_id,
                "client_secret": settings.get_password("provider_oauth_client_secret"),
            }
        )

        if response.status_code != 200:
            return {"success": False, "error": "Token refresh failed"}

        token_data = response.json()

        settings.provider_access_token = token_data.get("access_token")
        if token_data.get("refresh_token"):
            settings.provider_refresh_token = token_data.get("refresh_token")
        settings.save(ignore_permissions=True)

        return {"success": True}

    except requests.RequestException as e:
        frappe.log_error(f"Token refresh failed: {str(e)}")
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def disconnect():
    """
    Disconnect from provider

    Clears stored tokens
    """
    settings = frappe.get_single("WhatsApp Settings")
    settings.provider_access_token = ""
    settings.provider_refresh_token = ""
    settings.save(ignore_permissions=True)

    return {"success": True, "message": "Disconnected from provider"}


@frappe.whitelist()
def check_connection():
    """
    Check if connected to provider

    Returns:
        dict: Connection status
    """
    settings = frappe.get_single("WhatsApp Settings")

    connected = bool(settings.provider_access_token)
    waba_configured = bool(settings.meta_waba_id and settings.meta_phone_number_id)

    return {
        "connected": connected,
        "waba_configured": waba_configured,
        "provider_url": settings.provider_url,
        "phone_number": settings.meta_phone_number if waba_configured else None,
    }


def get_provider_headers():
    """
    Get headers for provider API calls

    Returns:
        dict: Headers with Bearer token
    """
    settings = frappe.get_single("WhatsApp Settings")

    if not settings.provider_access_token:
        frappe.throw(_(ERR_NOT_CONFIGURED))

    return {
        "Authorization": f"Bearer {settings.get_password('provider_access_token')}",
        "Content-Type": "application/json",
    }
