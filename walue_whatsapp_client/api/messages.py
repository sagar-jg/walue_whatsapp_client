"""
Message Management API for Customer App

This module handles:
1. Sending template messages
2. Sending free-form messages (within 24hr window)
3. Message status tracking
4. Message history

ALL message logs are stored LOCALLY - we own this data
"""

import frappe
from frappe import _
import requests
from datetime import datetime, timedelta
import re

from walue_whatsapp_client.constants import (
    CONVERSATION_WINDOW_HOURS,
    MESSAGE_STATUS_QUEUED,
    MESSAGE_STATUS_SENT,
    MESSAGE_STATUS_DELIVERED,
    MESSAGE_STATUS_READ,
    MESSAGE_STATUS_FAILED,
    MESSAGE_TYPE_TEMPLATE,
    MESSAGE_TYPE_TEXT,
    MESSAGE_TYPE_MEDIA,
    DIRECTION_OUTBOUND,
    DIRECTION_INBOUND,
    PHONE_REGEX,
    MSG_MESSAGE_SENT,
    ERR_INVALID_PHONE,
    ERR_MESSAGE_FAILED,
    ERR_OUTSIDE_WINDOW,
    ERR_TEMPLATE_NOT_FOUND,
    ERR_NOT_CONFIGURED,
)
from walue_whatsapp_client.api.auth import get_provider_headers


def _validate_phone(phone: str) -> bool:
    """Validate E.164 phone number format"""
    return bool(re.match(PHONE_REGEX, phone))


def _get_settings():
    """Get WhatsApp Settings with validation"""
    settings = frappe.get_single("WhatsApp Settings")
    # Check for Meta API credentials (required for direct API access)
    if not settings.meta_access_token or not settings.meta_phone_number_id:
        frappe.throw(_(ERR_NOT_CONFIGURED))
    return settings


def _is_in_conversation_window(lead_id: str) -> bool:
    """
    Check if we're within 24hr conversation window

    Returns True if customer has sent a message in the last 24 hours
    """
    window_start = datetime.now() - timedelta(hours=CONVERSATION_WINDOW_HOURS)

    last_inbound = frappe.db.get_value(
        "WhatsApp Message Log",
        {
            "lead": lead_id,
            "direction": DIRECTION_INBOUND,
            "sent_at": [">=", window_start]
        },
        "sent_at"
    )

    return bool(last_inbound)


@frappe.whitelist()
def get_templates() -> dict:
    """
    Get available message templates from local cache

    Returns templates from local cache. Use sync_templates() to refresh from Meta API.

    Returns:
        dict: Templates list with success status
    """
    templates = frappe.get_all(
        "WhatsApp Template",
        filters={"status": "approved"},
        fields=["template_name", "category", "language", "components"]
    )

    # If cache is empty, auto-sync first time
    if not templates:
        sync_result = sync_templates()
        if sync_result.get("success"):
            templates = frappe.get_all(
                "WhatsApp Template",
                filters={"status": "approved"},
                fields=["template_name", "category", "language", "components"]
            )

    return {"success": True, "templates": templates}


@frappe.whitelist()
def sync_templates() -> dict:
    """
    Sync message templates from Meta WhatsApp Business API to local cache

    Fetches all templates from Meta and upserts them into WhatsApp Template DocType

    Returns:
        dict: Sync result with count of synced templates
    """
    settings = frappe.get_single("WhatsApp Settings")

    if not settings.meta_waba_id or not settings.meta_access_token:
        return {
            "success": False,
            "error": "WABA ID and Access Token are required. Please configure WhatsApp Settings."
        }

    waba_id = settings.meta_waba_id
    access_token = settings.get_password("meta_access_token")

    # Fetch templates from Meta API
    url = f"https://graph.facebook.com/v21.0/{waba_id}/message_templates"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    try:
        response = requests.get(url, headers=headers)
        response_data = response.json()

        if "error" in response_data:
            return {
                "success": False,
                "error": response_data["error"].get("message", "Failed to fetch templates")
            }

        templates = response_data.get("data", [])
        synced_count = 0

        for template in templates:
            template_name = template.get("name")
            status = template.get("status", "").lower()

            # Map Meta status to our status
            status_map = {
                "approved": "approved",
                "pending": "pending",
                "rejected": "rejected",
                "in_appeal": "pending",
                "pending_deletion": "rejected",
                "deleted": "rejected",
                "disabled": "rejected",
                "paused": "pending",
                "limit_exceeded": "pending"
            }
            local_status = status_map.get(status, "pending")

            # Check if template exists
            existing = frappe.db.exists("WhatsApp Template", template_name)

            if existing:
                # Update existing template
                doc = frappe.get_doc("WhatsApp Template", template_name)
                doc.category = template.get("category", "").lower()
                doc.language = template.get("language", "en_US")
                doc.status = local_status
                doc.components = frappe.as_json(template.get("components", []))
                doc.last_synced = datetime.now()
                doc.save(ignore_permissions=True)
            else:
                # Create new template
                doc = frappe.get_doc({
                    "doctype": "WhatsApp Template",
                    "template_name": template_name,
                    "category": template.get("category", "").lower(),
                    "language": template.get("language", "en_US"),
                    "status": local_status,
                    "components": frappe.as_json(template.get("components", [])),
                    "last_synced": datetime.now()
                })
                doc.insert(ignore_permissions=True)

            synced_count += 1

        frappe.db.commit()

        # Update last sync time in settings
        settings.last_sync = datetime.now()
        settings.save(ignore_permissions=True)

        return {
            "success": True,
            "synced_count": synced_count,
            "message": f"Successfully synced {synced_count} templates"
        }

    except requests.RequestException as e:
        frappe.log_error(f"Template sync failed: {str(e)}")
        return {
            "success": False,
            "error": f"API request failed: {str(e)}"
        }


@frappe.whitelist()
def send_template(lead_id: str, template_name: str, template_language: str = "en_US",
                  template_variables: dict = None, use_queue: bool = True) -> dict:
    """
    Send a template message to a lead

    Args:
        lead_id: CRM Lead document name
        template_name: Name of the approved template
        template_language: Language code
        template_variables: Variable values for template
        use_queue: If True (default), send via background queue. If False, send synchronously.

    Returns:
        dict: Message status with message_log_id
    """
    lead = frappe.get_doc("CRM Lead", lead_id)
    phone = lead.whatsapp_number or lead.mobile_no

    if not phone or not _validate_phone(phone):
        return {"success": False, "error": ERR_INVALID_PHONE}

    settings = _get_settings()

    if not settings.meta_phone_number_id or not settings.meta_access_token:
        return {"success": False, "error": "Phone Number ID and Access Token are required in WhatsApp Settings"}

    # Create local message log with QUEUED status
    message_log = frappe.get_doc({
        "doctype": "WhatsApp Message Log",
        "lead": lead_id,
        "direction": DIRECTION_OUTBOUND,
        "to_number": phone,
        "from_number": settings.meta_phone_number,
        "message_type": MESSAGE_TYPE_TEMPLATE,
        "template_name": template_name,
        "status": MESSAGE_STATUS_QUEUED,
    })
    message_log.insert(ignore_permissions=True)
    frappe.db.commit()

    if use_queue:
        # Enqueue the actual sending as a background job
        frappe.enqueue(
            "walue_whatsapp_client.api.messages._send_template_job",
            queue="short",
            message_log_id=message_log.name,
            template_name=template_name,
            template_language=template_language,
            template_variables=template_variables,
            phone=phone,
            lead_id=lead_id,
        )

        return {
            "success": True,
            "queued": True,
            "message_log_id": message_log.name,
            "message": "Message queued for sending",
        }
    else:
        # Send synchronously
        return _send_template_sync(
            message_log.name, template_name, template_language,
            template_variables, phone, lead_id
        )


def _send_template_job(message_log_id: str, template_name: str, template_language: str,
                       template_variables: dict, phone: str, lead_id: str):
    """Background job to send template message"""
    _send_template_sync(message_log_id, template_name, template_language,
                        template_variables, phone, lead_id)


def _send_template_sync(message_log_id: str, template_name: str, template_language: str,
                        template_variables: dict, phone: str, lead_id: str) -> dict:
    """Actually send the template message to Meta API"""
    message_log = frappe.get_doc("WhatsApp Message Log", message_log_id)
    settings = frappe.get_single("WhatsApp Settings")

    # Build template components
    components = []
    if template_variables:
        body_params = []
        for key, value in template_variables.items():
            body_params.append({"type": "text", "text": str(value)})

        if body_params:
            components.append({
                "type": "body",
                "parameters": body_params
            })

    # Build Meta API payload
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": template_language}
        }
    }

    if components:
        payload["template"]["components"] = components

    try:
        phone_number_id = settings.meta_phone_number_id
        access_token = settings.get_password("meta_access_token")

        response = requests.post(
            f"https://graph.facebook.com/v21.0/{phone_number_id}/messages",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            },
            json=payload
        )

        result = response.json()

        if "messages" in result and result["messages"]:
            message_id = result["messages"][0].get("id")
            message_log.message_id = message_id
            message_log.status = MESSAGE_STATUS_SENT
            message_log.sent_at = datetime.now()
            message_log.save(ignore_permissions=True)

            # Update lead
            current_count = frappe.db.get_value("CRM Lead", lead_id, "total_whatsapp_messages") or 0
            frappe.db.set_value("CRM Lead", lead_id, {
                "last_whatsapp_message": datetime.now(),
                "total_whatsapp_messages": current_count + 1
            }, update_modified=False)

            frappe.db.commit()

            # Notify UI via realtime
            frappe.publish_realtime(
                "whatsapp_message_status",
                {
                    "message_log_id": message_log.name,
                    "lead": lead_id,
                    "status": MESSAGE_STATUS_SENT,
                    "message_id": message_id,
                },
                after_commit=True
            )

            return {
                "success": True,
                "message_id": message_id,
                "message_log_id": message_log.name,
                "message": MSG_MESSAGE_SENT,
            }
        else:
            error_msg = result.get("error", {}).get("message", ERR_MESSAGE_FAILED)
            message_log.status = MESSAGE_STATUS_FAILED
            message_log.error_message = error_msg
            message_log.save(ignore_permissions=True)
            frappe.db.commit()

            frappe.publish_realtime(
                "whatsapp_message_status",
                {
                    "message_log_id": message_log.name,
                    "lead": lead_id,
                    "status": MESSAGE_STATUS_FAILED,
                    "error": error_msg,
                },
                after_commit=True
            )

            return {"success": False, "error": error_msg}

    except requests.RequestException as e:
        message_log.status = MESSAGE_STATUS_FAILED
        message_log.error_message = str(e)
        message_log.save(ignore_permissions=True)
        frappe.log_error(f"Template message failed: {str(e)}")
        return {"success": False, "error": ERR_MESSAGE_FAILED}


@frappe.whitelist()
def send_text(lead_id: str, text: str) -> dict:
    """
    Send a free-form text message to a lead

    Only works within 24hr conversation window

    Args:
        lead_id: CRM Lead document name
        text: Message text

    Returns:
        dict: Message status
    """
    # Check conversation window
    if not _is_in_conversation_window(lead_id):
        return {"success": False, "error": ERR_OUTSIDE_WINDOW}

    lead = frappe.get_doc("CRM Lead", lead_id)
    phone = lead.whatsapp_number or lead.mobile_no

    if not phone or not _validate_phone(phone):
        return {"success": False, "error": ERR_INVALID_PHONE}

    settings = _get_settings()

    # Create local message log
    message_log = frappe.get_doc({
        "doctype": "WhatsApp Message Log",
        "lead": lead_id,
        "direction": DIRECTION_OUTBOUND,
        "to_number": phone,
        "from_number": settings.meta_phone_number,
        "message_type": MESSAGE_TYPE_TEXT,
        "message_content": text,
        "status": MESSAGE_STATUS_QUEUED,
        "sent_at": datetime.now(),
    })
    message_log.insert(ignore_permissions=True)

    try:
        response = requests.post(
            f"{settings.provider_url}/api/method/walue_whatsapp_provider.api.messages.send_text",
            headers=get_provider_headers(),
            json={
                "phone_number_id": settings.meta_phone_number_id,
                "access_token": settings.get_password("meta_access_token"),
                "to": phone,
                "text": text,
            }
        )

        result = response.json()

        if result.get("success"):
            message_log.message_id = result.get("message_id")
            message_log.status = MESSAGE_STATUS_SENT
            message_log.cost = result.get("cost", 0)
            message_log.save(ignore_permissions=True)

            lead.last_whatsapp_message = datetime.now()
            lead.total_whatsapp_messages = (lead.total_whatsapp_messages or 0) + 1
            lead.save(ignore_permissions=True)

            return {
                "success": True,
                "message_id": result.get("message_id"),
                "message_log_id": message_log.name,
            }
        else:
            message_log.status = MESSAGE_STATUS_FAILED
            message_log.error_message = result.get("error")
            message_log.save(ignore_permissions=True)
            return {"success": False, "error": result.get("error", ERR_MESSAGE_FAILED)}

    except requests.RequestException as e:
        message_log.status = MESSAGE_STATUS_FAILED
        message_log.error_message = str(e)
        message_log.save(ignore_permissions=True)
        frappe.log_error(f"Text message failed: {str(e)}")
        return {"success": False, "error": ERR_MESSAGE_FAILED}


@frappe.whitelist()
def update_status(message_log_id: str, status: str, timestamp: str = None) -> dict:
    """
    Update message status from webhook

    Args:
        message_log_id: WhatsApp Message Log document name
        status: New status (sent, delivered, read, failed)
        timestamp: Status timestamp

    Returns:
        dict: Update result
    """
    if status not in [MESSAGE_STATUS_SENT, MESSAGE_STATUS_DELIVERED, MESSAGE_STATUS_READ, MESSAGE_STATUS_FAILED]:
        return {"success": False, "error": "Invalid status"}

    message_log = frappe.get_doc("WhatsApp Message Log", message_log_id)
    message_log.status = status

    if timestamp:
        ts = datetime.fromtimestamp(int(timestamp))
        if status == MESSAGE_STATUS_DELIVERED:
            message_log.delivered_at = ts
        elif status == MESSAGE_STATUS_READ:
            message_log.read_at = ts

    message_log.save(ignore_permissions=True)

    return {"success": True}


@frappe.whitelist()
def get_message_history(lead_id: str, limit: int = 50) -> list:
    """
    Get message history for a lead

    Args:
        lead_id: CRM Lead document name
        limit: Max records

    Returns:
        list: Message log records
    """
    return frappe.get_all(
        "WhatsApp Message Log",
        filters={"lead": lead_id},
        fields=["name", "direction", "message_type", "template_name", "message_content",
                "status", "sent_at", "delivered_at", "read_at", "error_message"],
        order_by="sent_at desc",
        limit=limit
    )


@frappe.whitelist()
def check_conversation_window(lead_id: str) -> dict:
    """
    Check conversation window status for a lead

    Args:
        lead_id: CRM Lead document name

    Returns:
        dict: Window status and time remaining
    """
    window_start = datetime.now() - timedelta(hours=CONVERSATION_WINDOW_HOURS)

    last_inbound = frappe.db.get_value(
        "WhatsApp Message Log",
        {
            "lead": lead_id,
            "direction": DIRECTION_INBOUND,
            "sent_at": [">=", window_start]
        },
        "sent_at"
    )

    if last_inbound:
        last_time = datetime.strptime(str(last_inbound), "%Y-%m-%d %H:%M:%S")
        expires_at = last_time + timedelta(hours=CONVERSATION_WINDOW_HOURS)
        remaining = (expires_at - datetime.now()).total_seconds()

        return {
            "in_window": True,
            "expires_at": expires_at.isoformat(),
            "remaining_seconds": max(0, int(remaining)),
            "can_send_text": True,
        }

    return {
        "in_window": False,
        "can_send_text": False,
        "message": "Use template message to start conversation",
    }
