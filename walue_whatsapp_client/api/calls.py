"""
Call Management API for Customer App

This module handles:
1. Permission checking (from local records)
2. Permission request (via provider)
3. Call initiation (via provider's Janus)
4. Call logging (stored locally)
5. Call termination

ALL call logs are stored LOCALLY - we own this data
"""

import frappe
from frappe import _
import requests
from datetime import datetime, timedelta
import re

from walue_whatsapp_client.constants import (
    CALL_PERMISSION_DAILY_LIMIT,
    CALL_PERMISSION_WEEKLY_LIMIT,
    MAX_CALLS_AFTER_PERMISSION,
    PERMISSION_VALIDITY_DAYS,
    PERMISSION_STATUS_NONE,
    PERMISSION_STATUS_REQUESTED,
    PERMISSION_STATUS_GRANTED,
    PERMISSION_STATUS_EXPIRED,
    CALL_STATUS_INITIATING,
    CALL_STATUS_ENDED,
    CALL_STATUS_FAILED,
    CALL_DIRECTION_OUTBOUND,
    PHONE_REGEX,
    MSG_PERMISSION_REQUIRED,
    MSG_PERMISSION_PENDING,
    MSG_PERMISSION_GRANTED,
    MSG_PERMISSION_EXPIRED,
    MSG_DAILY_LIMIT,
    MSG_WEEKLY_LIMIT,
    MSG_CALL_LIMIT,
    ERR_NO_PERMISSION,
    ERR_INVALID_PHONE,
    ERR_CALL_FAILED,
    ERR_NOT_CONFIGURED,
)
from walue_whatsapp_client.api.auth import get_provider_headers


def _validate_phone(phone: str) -> bool:
    """Validate E.164 phone number format"""
    return bool(re.match(PHONE_REGEX, phone))


def _get_settings():
    """Get WhatsApp Settings with validation"""
    settings = frappe.get_single("WhatsApp Settings")
    if not settings.provider_access_token:
        frappe.throw(_(ERR_NOT_CONFIGURED))
    return settings


@frappe.whitelist()
def check_permission(lead_id: str) -> dict:
    """
    Check call permission status for a lead

    Checks LOCAL WhatsApp Call Permission record

    Args:
        lead_id: CRM Lead document name

    Returns:
        dict: Permission status and details
    """
    lead = frappe.get_doc("CRM Lead", lead_id)
    phone = lead.whatsapp_number or lead.mobile_no

    if not phone:
        return {
            "status": "no_phone",
            "message": "No WhatsApp number on this lead",
            "can_call": False,
        }

    if not _validate_phone(phone):
        return {
            "status": "invalid_phone",
            "message": ERR_INVALID_PHONE,
            "can_call": False,
        }

    # Check local permission record
    permission = frappe.db.get_value(
        "WhatsApp Call Permission",
        {"lead": lead_id},
        ["name", "permission_status", "granted_at", "expires_at", "calls_made_count",
         "request_count_24h", "request_count_7d", "last_request_sent_at"],
        as_dict=True
    )

    if not permission:
        return {
            "status": PERMISSION_STATUS_NONE,
            "message": MSG_PERMISSION_REQUIRED,
            "can_call": False,
            "can_request": True,
        }

    now = datetime.now()

    # Check if permission is expired
    if permission.permission_status == PERMISSION_STATUS_GRANTED:
        if permission.expires_at and datetime.strptime(str(permission.expires_at), "%Y-%m-%d %H:%M:%S") < now:
            # Update status to expired
            frappe.db.set_value("WhatsApp Call Permission", permission.name, "permission_status", PERMISSION_STATUS_EXPIRED)
            return {
                "status": PERMISSION_STATUS_EXPIRED,
                "message": MSG_PERMISSION_EXPIRED,
                "can_call": False,
                "can_request": True,
            }

        # Check daily call limit
        if permission.calls_made_count >= MAX_CALLS_AFTER_PERMISSION:
            return {
                "status": PERMISSION_STATUS_GRANTED,
                "message": MSG_CALL_LIMIT,
                "can_call": False,
                "can_request": False,
                "calls_remaining": 0,
            }

        return {
            "status": PERMISSION_STATUS_GRANTED,
            "message": MSG_PERMISSION_GRANTED,
            "can_call": True,
            "expires_at": permission.expires_at,
            "calls_remaining": MAX_CALLS_AFTER_PERMISSION - permission.calls_made_count,
        }

    if permission.permission_status == PERMISSION_STATUS_REQUESTED:
        return {
            "status": PERMISSION_STATUS_REQUESTED,
            "message": MSG_PERMISSION_PENDING,
            "can_call": False,
            "can_request": False,
        }

    if permission.permission_status == PERMISSION_STATUS_EXPIRED:
        # Check if can request again
        can_request = _can_request_permission(permission)
        return {
            "status": PERMISSION_STATUS_EXPIRED,
            "message": MSG_PERMISSION_EXPIRED if can_request else MSG_WEEKLY_LIMIT,
            "can_call": False,
            "can_request": can_request,
        }

    return {
        "status": permission.permission_status,
        "can_call": False,
        "can_request": _can_request_permission(permission),
    }


def _can_request_permission(permission: dict) -> bool:
    """Check if another permission request can be sent"""
    now = datetime.now()

    # Check 24h limit
    if permission.last_request_sent_at:
        last_request = datetime.strptime(str(permission.last_request_sent_at), "%Y-%m-%d %H:%M:%S")
        if (now - last_request).total_seconds() < 86400:  # 24 hours
            if permission.request_count_24h >= CALL_PERMISSION_DAILY_LIMIT:
                return False

    # Check 7-day limit
    if permission.request_count_7d >= CALL_PERMISSION_WEEKLY_LIMIT:
        return False

    return True


@frappe.whitelist()
def request_permission(lead_id: str) -> dict:
    """
    Send call permission request for a lead

    Creates/updates local permission record and sends request via provider

    Args:
        lead_id: CRM Lead document name

    Returns:
        dict: Request status
    """
    lead = frappe.get_doc("CRM Lead", lead_id)
    phone = lead.whatsapp_number or lead.mobile_no

    if not phone or not _validate_phone(phone):
        return {"success": False, "error": ERR_INVALID_PHONE}

    settings = _get_settings()

    # Get or create permission record
    existing = frappe.db.get_value("WhatsApp Call Permission", {"lead": lead_id}, "name")

    if existing:
        permission = frappe.get_doc("WhatsApp Call Permission", existing)

        # Validate can request
        if not _can_request_permission(permission.as_dict()):
            return {
                "success": False,
                "error": MSG_WEEKLY_LIMIT if permission.request_count_7d >= CALL_PERMISSION_WEEKLY_LIMIT else MSG_DAILY_LIMIT
            }
    else:
        permission = frappe.get_doc({
            "doctype": "WhatsApp Call Permission",
            "lead": lead_id,
            "phone_number": phone,
            "permission_status": PERMISSION_STATUS_NONE,
            "request_count_24h": 0,
            "request_count_7d": 0,
            "calls_made_count": 0,
        })
        permission.insert(ignore_permissions=True)

    # Send request via provider
    try:
        response = requests.post(
            f"{settings.provider_url}/api/method/walue_whatsapp_provider.api.calls.request_permission",
            headers=get_provider_headers(),
            json={
                "phone_number_id": settings.meta_phone_number_id,
                "access_token": settings.get_password("meta_access_token"),
                "to": phone,
                "use_template": True,  # Use template for outside 24h window
            }
        )

        result = response.json()

        if result.get("success"):
            # Update local record
            permission.permission_status = PERMISSION_STATUS_REQUESTED
            permission.last_request_sent_at = datetime.now()
            permission.request_count_24h = (permission.request_count_24h or 0) + 1
            permission.request_count_7d = (permission.request_count_7d or 0) + 1
            permission.save(ignore_permissions=True)

            # Update lead
            lead.whatsapp_call_permission_status = PERMISSION_STATUS_REQUESTED
            lead.save(ignore_permissions=True)

            return {
                "success": True,
                "message": MSG_PERMISSION_PENDING,
            }
        else:
            return {
                "success": False,
                "error": result.get("error", "Failed to send permission request"),
            }

    except requests.RequestException as e:
        frappe.log_error(f"Permission request failed: {str(e)}")
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def initiate(lead_id: str) -> dict:
    """
    Initiate a WhatsApp call to a lead

    Creates local call log and gets WebRTC credentials from provider

    Args:
        lead_id: CRM Lead document name

    Returns:
        dict: WebRTC connection details
    """
    lead = frappe.get_doc("CRM Lead", lead_id)
    phone = lead.whatsapp_number or lead.mobile_no

    if not phone or not _validate_phone(phone):
        return {"success": False, "error": ERR_INVALID_PHONE}

    # Check permission
    permission_check = check_permission(lead_id)
    if not permission_check.get("can_call"):
        return {"success": False, "error": permission_check.get("message", ERR_NO_PERMISSION)}

    settings = _get_settings()

    # Create local call log
    call_log = frappe.get_doc({
        "doctype": "WhatsApp Call Log",
        "lead": lead_id,
        "direction": CALL_DIRECTION_OUTBOUND,
        "to_number": phone,
        "from_number": settings.meta_phone_number,
        "status": CALL_STATUS_INITIATING,
        "started_at": datetime.now(),
    })
    call_log.insert(ignore_permissions=True)

    try:
        # Get WebRTC credentials from provider
        response = requests.post(
            f"{settings.provider_url}/api/method/walue_whatsapp_provider.api.calls.initiate",
            headers=get_provider_headers(),
            json={
                "phone_number_id": settings.meta_phone_number_id,
                "access_token": settings.get_password("meta_access_token"),
                "to": phone,
                "from_number": settings.meta_phone_number,
            }
        )

        result = response.json()

        if result.get("success"):
            # Update call log with session ID
            call_log.call_session_id = result.get("call_session_id")
            call_log.save(ignore_permissions=True)

            # Update permission call count
            permission = frappe.get_doc("WhatsApp Call Permission", {"lead": lead_id})
            permission.calls_made_count = (permission.calls_made_count or 0) + 1
            permission.last_call_at = datetime.now()
            permission.save(ignore_permissions=True)

            return {
                "success": True,
                "call_log_id": call_log.name,
                "call_session_id": result.get("call_session_id"),
                "janus_session_id": result.get("janus_session_id"),
                "janus_handle_id": result.get("janus_handle_id"),
                "janus_ws_url": result.get("janus_ws_url"),
                "ice_servers": result.get("ice_servers"),
            }
        else:
            call_log.status = CALL_STATUS_FAILED
            call_log.save(ignore_permissions=True)
            return {"success": False, "error": result.get("error", ERR_CALL_FAILED)}

    except requests.RequestException as e:
        call_log.status = CALL_STATUS_FAILED
        call_log.save(ignore_permissions=True)
        frappe.log_error(f"Call initiation failed: {str(e)}")
        return {"success": False, "error": ERR_CALL_FAILED}


@frappe.whitelist()
def end(call_log_id: str, notes: str = None) -> dict:
    """
    End a call and update local log

    Args:
        call_log_id: WhatsApp Call Log document name
        notes: Optional call notes

    Returns:
        dict: Call summary with cost
    """
    call_log = frappe.get_doc("WhatsApp Call Log", call_log_id)

    if call_log.status == CALL_STATUS_ENDED:
        return {"success": False, "error": "Call already ended"}

    # Calculate duration
    ended_at = datetime.now()
    started_at = datetime.strptime(str(call_log.started_at), "%Y-%m-%d %H:%M:%S")
    duration_seconds = int((ended_at - started_at).total_seconds())

    settings = _get_settings()

    try:
        # Notify provider
        response = requests.post(
            f"{settings.provider_url}/api/method/walue_whatsapp_provider.api.calls.end",
            headers=get_provider_headers(),
            json={
                "call_session_id": call_log.call_session_id,
                "duration_seconds": duration_seconds,
            }
        )

        result = response.json()
        cost = result.get("cost", 0)

    except requests.RequestException:
        cost = 0

    # Update local call log
    call_log.status = CALL_STATUS_ENDED
    call_log.ended_at = ended_at
    call_log.duration_seconds = duration_seconds
    call_log.cost = cost
    if notes:
        call_log.notes = notes
    call_log.save(ignore_permissions=True)

    # Update lead
    lead = frappe.get_doc("CRM Lead", call_log.lead)
    lead.last_whatsapp_call = ended_at
    lead.total_whatsapp_calls = (lead.total_whatsapp_calls or 0) + 1
    lead.save(ignore_permissions=True)

    return {
        "success": True,
        "duration_seconds": duration_seconds,
        "cost": cost,
    }


@frappe.whitelist()
def get_call_history(lead_id: str, limit: int = 20) -> list:
    """
    Get call history for a lead

    Args:
        lead_id: CRM Lead document name
        limit: Max records to return

    Returns:
        list: Call log records
    """
    return frappe.get_all(
        "WhatsApp Call Log",
        filters={"lead": lead_id},
        fields=["name", "direction", "status", "started_at", "ended_at",
                "duration_seconds", "cost", "notes"],
        order_by="started_at desc",
        limit=limit
    )
