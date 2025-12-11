"""
WhatsApp Call Permission DocType

Tracks call permission status for each lead/phone number.

Meta's Call Permission Rules:
- 1 permission request per 24 hours
- 2 permission requests per 7 days
- Permission valid for 7 days
- Max 5 calls per 24 hours after permission granted
- Permission auto-revoked after 4 unanswered calls

This data is stored LOCALLY in customer's system.
"""

import frappe
from frappe.model.document import Document
from datetime import datetime, timedelta


class WhatsAppCallPermission(Document):
    def validate(self):
        """Validate permission record"""
        # Validate phone number format
        if self.phone_number and not self.phone_number.startswith("+"):
            frappe.msgprint("Phone number should be in E.164 format (e.g., +919876543210)")

    def on_update(self):
        """Update lead's permission status"""
        if self.lead and self.has_value_changed("permission_status"):
            frappe.db.set_value(
                "CRM Lead",
                self.lead,
                "whatsapp_call_permission_status",
                self.permission_status
            )

    def can_request_permission(self):
        """Check if another permission request can be sent"""
        # Check 24h limit (max 1 request)
        if self.request_count_24h >= 1:
            return False, "Daily limit reached (1 request per 24 hours)"

        # Check 7-day limit (max 2 requests)
        if self.request_count_7d >= 2:
            return False, "Weekly limit reached (2 requests per 7 days)"

        return True, None

    def can_make_call(self):
        """Check if a call can be made"""
        # Must have granted permission
        if self.permission_status != "granted":
            return False, f"Permission status is {self.permission_status}"

        # Check if permission expired
        if self.expires_at:
            expires = datetime.strptime(str(self.expires_at), "%Y-%m-%d %H:%M:%S")
            if expires < datetime.now():
                self.permission_status = "expired"
                self.save(ignore_permissions=True)
                return False, "Permission has expired"

        # Check daily call limit (max 5)
        if self.calls_made_count >= 5:
            return False, "Daily call limit reached (5 calls per 24 hours)"

        return True, None

    def record_permission_request(self):
        """Record that a permission request was sent"""
        now = datetime.now()

        self.last_request_sent_at = now
        self.request_count_24h = (self.request_count_24h or 0) + 1
        self.request_count_7d = (self.request_count_7d or 0) + 1
        self.permission_status = "requested"

        self.save(ignore_permissions=True)

    def record_permission_granted(self, expires_at=None):
        """Record that permission was granted"""
        now = datetime.now()

        self.permission_status = "granted"
        self.granted_at = now
        self.expires_at = expires_at or (now + timedelta(days=7))
        self.calls_made_count = 0  # Reset call counter

        self.save(ignore_permissions=True)

    def record_call_made(self):
        """Record that a call was made"""
        self.calls_made_count = (self.calls_made_count or 0) + 1
        self.last_call_at = datetime.now()
        self.save(ignore_permissions=True)

    def get_status_indicator(self):
        """Get status indicator color for UI"""
        indicators = {
            "none": "gray",
            "requested": "orange",
            "granted": "green",
            "expired": "red",
            "revoked": "red",
        }
        return indicators.get(self.permission_status, "gray")
