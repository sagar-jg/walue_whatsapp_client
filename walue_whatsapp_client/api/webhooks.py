"""
Webhook Handlers for Customer App

This module receives webhooks forwarded from the provider for:
1. Message status updates
2. Inbound messages
3. Call permission responses

All data is stored locally in the customer's Frappe instance.
"""

import frappe
from frappe import _
import hmac
import hashlib
from datetime import datetime, timedelta

from walue_whatsapp_client.constants import (
    MESSAGE_STATUS_SENT,
    MESSAGE_STATUS_DELIVERED,
    MESSAGE_STATUS_READ,
    MESSAGE_STATUS_FAILED,
    PERMISSION_STATUS_GRANTED,
    PERMISSION_STATUS_EXPIRED,
    PERMISSION_VALIDITY_DAYS,
    DIRECTION_INBOUND,
    MESSAGE_TYPE_TEXT,
)


def _verify_signature() -> bool:
    """Verify webhook signature from provider"""
    signature_header = frappe.request.headers.get("X-Walue-Signature", "")

    if not signature_header.startswith("sha256="):
        return False

    expected_signature = signature_header[7:]

    settings = frappe.get_single("WhatsApp Settings")
    # Use provider client secret for verification
    secret = settings.get_password("provider_oauth_client_secret")

    if not secret:
        return False

    payload = frappe.request.data
    calculated = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(calculated, expected_signature)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def receive():
    """
    Receive webhooks forwarded from provider

    Stores all data locally
    """
    # Verify signature
    if not _verify_signature():
        frappe.log_error("Invalid webhook signature from provider")
        frappe.throw(_("Invalid signature"), frappe.AuthenticationError)

    try:
        data = frappe.parse_json(frappe.request.data)
    except Exception:
        return {"status": "error", "message": "Invalid payload"}

    webhook_type = data.get("type")

    if webhook_type == "message_status":
        _handle_message_status(data)
    elif webhook_type == "inbound_message":
        _handle_inbound_message(data)
    elif webhook_type == "call_permission_reply":
        _handle_call_permission_reply(data)
    elif webhook_type == "call_status":
        _handle_call_status(data)

    return {"status": "ok"}


def _handle_message_status(data: dict):
    """
    Handle message status update webhook

    Updates local WhatsApp Message Log with new status
    """
    message_id = data.get("message_id")
    status = data.get("status")
    timestamp = data.get("timestamp")

    if not message_id or not status:
        return

    # Map Meta status to our status
    status_map = {
        "sent": MESSAGE_STATUS_SENT,
        "delivered": MESSAGE_STATUS_DELIVERED,
        "read": MESSAGE_STATUS_READ,
        "failed": MESSAGE_STATUS_FAILED,
    }

    mapped_status = status_map.get(status)
    if not mapped_status:
        return

    # Find message log by message_id
    message_log_name = frappe.db.get_value(
        "WhatsApp Message Log",
        {"message_id": message_id},
        "name"
    )

    if not message_log_name:
        frappe.log_error(f"Message log not found for message_id: {message_id}")
        return

    message_log = frappe.get_doc("WhatsApp Message Log", message_log_name)

    # Only update if status progresses forward
    status_order = [MESSAGE_STATUS_SENT, MESSAGE_STATUS_DELIVERED, MESSAGE_STATUS_READ]

    if mapped_status == MESSAGE_STATUS_FAILED:
        message_log.status = MESSAGE_STATUS_FAILED
        message_log.error_message = data.get("errors", [{}])[0].get("message", "Unknown error")
    elif mapped_status in status_order:
        current_index = status_order.index(message_log.status) if message_log.status in status_order else -1
        new_index = status_order.index(mapped_status)

        if new_index > current_index:
            message_log.status = mapped_status

            if timestamp:
                ts = datetime.fromtimestamp(int(timestamp))
                if mapped_status == MESSAGE_STATUS_DELIVERED:
                    message_log.delivered_at = ts
                elif mapped_status == MESSAGE_STATUS_READ:
                    message_log.read_at = ts

    message_log.save(ignore_permissions=True)
    frappe.db.commit()

    # Trigger real-time update
    frappe.publish_realtime(
        "whatsapp_message_status",
        {
            "message_log_id": message_log.name,
            "lead": message_log.lead,
            "status": message_log.status,
        },
        doctype="WhatsApp Message Log",
        docname=message_log.name
    )


def _handle_inbound_message(data: dict):
    """
    Handle inbound message webhook

    Creates new WhatsApp Message Log for inbound message
    Opens 24hr conversation window
    """
    from_number = data.get("from")
    message_id = data.get("message_id")
    message_type = data.get("message_type", "text")
    text = data.get("text")
    timestamp = data.get("timestamp")

    if not from_number or not message_id:
        return

    settings = frappe.get_single("WhatsApp Settings")

    # Find lead by phone number
    lead = frappe.db.get_value(
        "CRM Lead",
        {"whatsapp_number": from_number},
        ["name", "lead_name"],
        as_dict=True
    )

    if not lead:
        # Try mobile_no field
        lead = frappe.db.get_value(
            "CRM Lead",
            {"mobile_no": from_number},
            ["name", "lead_name"],
            as_dict=True
        )

    if not lead:
        frappe.log_error(f"No lead found for phone: {from_number}")
        # Could create a new lead here or store in unassigned messages
        return

    # Create message log
    message_log = frappe.get_doc({
        "doctype": "WhatsApp Message Log",
        "lead": lead.name,
        "message_id": message_id,
        "direction": DIRECTION_INBOUND,
        "from_number": from_number,
        "to_number": settings.meta_phone_number,
        "message_type": MESSAGE_TYPE_TEXT,
        "message_content": text,
        "status": MESSAGE_STATUS_DELIVERED,  # Inbound is already delivered
        "sent_at": datetime.fromtimestamp(int(timestamp)) if timestamp else datetime.now(),
        "delivered_at": datetime.now(),
    })
    message_log.insert(ignore_permissions=True)

    # Update lead
    frappe.db.set_value("CRM Lead", lead.name, {
        "last_whatsapp_message": datetime.now(),
        "total_whatsapp_messages": (frappe.db.get_value("CRM Lead", lead.name, "total_whatsapp_messages") or 0) + 1
    })

    frappe.db.commit()

    # Trigger real-time notification
    frappe.publish_realtime(
        "whatsapp_new_message",
        {
            "lead": lead.name,
            "lead_name": lead.lead_name,
            "from_number": from_number,
            "message": text[:100] if text else "New message",
            "message_log_id": message_log.name,
        },
        user=frappe.session.user
    )


def _handle_call_permission_reply(data: dict):
    """
    Handle call permission reply webhook

    Updates local WhatsApp Call Permission record
    """
    from_number = data.get("from")
    response = data.get("response")  # "ACCEPT" or "DECLINE"
    expiration = data.get("expiration")

    if not from_number or not response:
        return

    # Find permission record by phone number
    permission = frappe.db.get_value(
        "WhatsApp Call Permission",
        {"phone_number": from_number, "permission_status": "requested"},
        "name"
    )

    if not permission:
        frappe.log_error(f"No pending permission found for: {from_number}")
        return

    perm_doc = frappe.get_doc("WhatsApp Call Permission", permission)

    if response == "ACCEPT":
        perm_doc.permission_status = PERMISSION_STATUS_GRANTED
        perm_doc.granted_at = datetime.now()

        # Set expiry
        if expiration:
            perm_doc.expires_at = datetime.fromtimestamp(int(expiration))
        else:
            perm_doc.expires_at = datetime.now() + timedelta(days=PERMISSION_VALIDITY_DAYS)

        perm_doc.calls_made_count = 0  # Reset call counter
    else:
        # Declined - keep as requested or set to a declined status
        pass

    perm_doc.save(ignore_permissions=True)

    # Update lead
    if perm_doc.lead:
        frappe.db.set_value(
            "CRM Lead",
            perm_doc.lead,
            "whatsapp_call_permission_status",
            perm_doc.permission_status
        )

    frappe.db.commit()

    # Notify user
    frappe.publish_realtime(
        "whatsapp_permission_update",
        {
            "lead": perm_doc.lead,
            "phone_number": from_number,
            "status": perm_doc.permission_status,
            "can_call": perm_doc.permission_status == PERMISSION_STATUS_GRANTED,
        }
    )


def _handle_call_status(data: dict):
    """
    Handle call status update webhook

    Updates local WhatsApp Call Log
    """
    call_session_id = data.get("call_session_id")
    status = data.get("status")

    if not call_session_id or not status:
        return

    call_log_name = frappe.db.get_value(
        "WhatsApp Call Log",
        {"call_session_id": call_session_id},
        "name"
    )

    if not call_log_name:
        return

    frappe.db.set_value("WhatsApp Call Log", call_log_name, "status", status)
    frappe.db.commit()

    # Notify UI
    frappe.publish_realtime(
        "whatsapp_call_status",
        {
            "call_log_id": call_log_name,
            "status": status,
        }
    )
