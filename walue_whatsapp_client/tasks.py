"""
Scheduled Tasks for Walue WhatsApp Client

These tasks run on schedule as defined in hooks.py:
- All (every minute): Poll message status
- Hourly: Sync templates, Report usage to provider
- Daily: Check permission expiry
"""

import frappe
from frappe import _
from datetime import datetime, timedelta
import requests

from walue_whatsapp_client.constants import (
    MESSAGE_STATUS_SENT,
    MESSAGE_STATUS_DELIVERED,
    PERMISSION_STATUS_GRANTED,
    PERMISSION_STATUS_EXPIRED,
)


def poll_message_status():
    """
    Poll message status for pending messages

    Fallback when webhooks are not received
    Runs every minute but only checks messages older than 5 minutes
    """
    settings = frappe.get_single("WhatsApp Settings")

    if not settings.meta_access_token:
        return

    # Get messages that are sent but not yet delivered (older than 5 min)
    cutoff = datetime.now() - timedelta(minutes=5)

    pending_messages = frappe.get_all(
        "WhatsApp Message Log",
        filters={
            "status": MESSAGE_STATUS_SENT,
            "sent_at": ["<", cutoff],
            "message_id": ["is", "set"]
        },
        fields=["name", "message_id"],
        limit=20
    )

    if not pending_messages:
        return

    access_token = settings.get_password("meta_access_token")

    for msg in pending_messages:
        try:
            # Query Meta API for message status
            url = f"https://graph.facebook.com/v21.0/{msg.message_id}"
            headers = {"Authorization": f"Bearer {access_token}"}

            response = requests.get(url, headers=headers)

            if response.status_code == 200:
                data = response.json()
                status = data.get("status")

                if status and status != MESSAGE_STATUS_SENT:
                    frappe.db.set_value(
                        "WhatsApp Message Log",
                        msg.name,
                        "status",
                        status
                    )

        except requests.RequestException:
            pass

    frappe.db.commit()


def sync_templates():
    """
    Sync message templates from WABA

    Runs hourly to keep templates up to date
    """
    from walue_whatsapp_client.api.setup import sync_templates as do_sync

    try:
        result = do_sync()
        if result.get("success"):
            frappe.logger().info(f"Template sync: {result.get('count')} templates")
        else:
            frappe.log_error(f"Template sync failed: {result.get('error')}")
    except Exception as e:
        frappe.log_error(f"Template sync error: {str(e)}")


def report_usage_to_provider():
    """
    Report usage metrics to provider

    Sends aggregated counts only (no individual details)
    Runs hourly
    """
    settings = frappe.get_single("WhatsApp Settings")

    if not settings.provider_url or not settings.provider_access_token:
        return

    # Get hourly usage counts
    last_hour = datetime.now() - timedelta(hours=1)

    # Count calls
    call_count = frappe.db.count(
        "WhatsApp Call Log",
        filters={"started_at": [">=", last_hour]}
    )

    # Sum call duration
    call_duration = frappe.db.sql("""
        SELECT COALESCE(SUM(duration_seconds), 0) as total
        FROM `tabWhatsApp Call Log`
        WHERE started_at >= %s
    """, (last_hour,))[0][0] or 0

    # Count messages
    message_count = frappe.db.count(
        "WhatsApp Message Log",
        filters={
            "sent_at": [">=", last_hour],
            "direction": "outbound"
        }
    )

    # Only report if there's activity
    if call_count == 0 and message_count == 0:
        return

    try:
        headers = {
            "Authorization": f"Bearer {settings.get_password('provider_access_token')}",
            "Content-Type": "application/json",
        }

        # Report call usage
        if call_count > 0:
            requests.post(
                f"{settings.provider_url}/api/method/walue_whatsapp_provider.api.metrics.report_usage",
                headers=headers,
                json={
                    "usage_type": "call",
                    "count": call_count,
                    "duration_minutes": call_duration / 60,
                    "cost": 0,  # Cost is calculated by provider
                }
            )

        # Report message usage
        if message_count > 0:
            requests.post(
                f"{settings.provider_url}/api/method/walue_whatsapp_provider.api.metrics.report_usage",
                headers=headers,
                json={
                    "usage_type": "message",
                    "count": message_count,
                    "cost": 0,
                }
            )

        frappe.logger().info(f"Usage reported: {call_count} calls, {message_count} messages")

    except requests.RequestException as e:
        frappe.log_error(f"Usage reporting failed: {str(e)}")


def check_permission_expiry():
    """
    Check and update expired call permissions

    Runs daily to mark expired permissions
    """
    now = datetime.now()

    # Find expired permissions
    expired = frappe.get_all(
        "WhatsApp Call Permission",
        filters={
            "permission_status": PERMISSION_STATUS_GRANTED,
            "expires_at": ["<", now]
        },
        pluck="name"
    )

    if not expired:
        return

    for perm_name in expired:
        perm = frappe.get_doc("WhatsApp Call Permission", perm_name)
        perm.permission_status = PERMISSION_STATUS_EXPIRED
        perm.save(ignore_permissions=True)

        # Update lead
        if perm.lead:
            frappe.db.set_value(
                "CRM Lead",
                perm.lead,
                "whatsapp_call_permission_status",
                PERMISSION_STATUS_EXPIRED
            )

    frappe.db.commit()
    frappe.logger().info(f"Marked {len(expired)} permissions as expired")


def reset_daily_counters():
    """
    Reset daily request counters

    Runs daily at midnight
    """
    frappe.db.sql("""
        UPDATE `tabWhatsApp Call Permission`
        SET request_count_24h = 0,
            calls_made_count = 0
        WHERE request_count_24h > 0
        OR calls_made_count > 0
    """)

    frappe.db.commit()


def reset_weekly_counters():
    """
    Reset weekly request counters

    Runs weekly
    """
    frappe.db.sql("""
        UPDATE `tabWhatsApp Call Permission`
        SET request_count_7d = 0
        WHERE request_count_7d > 0
    """)

    frappe.db.commit()
