"""
WhatsApp Call Log DocType

Stores ALL call logs LOCALLY in customer's system.

This includes:
- Call details (to/from numbers)
- Duration and timing
- Recording links (if enabled)
- Cost information
- Notes

IMPORTANT: This data stays in customer's system. Provider only receives
aggregated counts and durations for billing.
"""

import frappe
from frappe.model.document import Document
from datetime import datetime


class WhatsAppCallLog(Document):
    def before_insert(self):
        """Set defaults before insert"""
        if not self.started_at:
            self.started_at = datetime.now()

    def validate(self):
        """Validate call log"""
        # Calculate duration if ended
        if self.ended_at and self.started_at:
            started = datetime.strptime(str(self.started_at), "%Y-%m-%d %H:%M:%S")
            ended = datetime.strptime(str(self.ended_at), "%Y-%m-%d %H:%M:%S")
            self.duration_seconds = int((ended - started).total_seconds())

    def on_update(self):
        """Update lead on call status change"""
        if self.has_value_changed("status") and self.status == "ended":
            self._update_lead_stats()

    def _update_lead_stats(self):
        """Update lead's WhatsApp call statistics"""
        if not self.lead:
            return

        try:
            lead = frappe.get_doc("CRM Lead", self.lead)
            lead.last_whatsapp_call = self.ended_at or self.started_at

            # Count total calls
            total = frappe.db.count("WhatsApp Call Log", {"lead": self.lead})
            lead.total_whatsapp_calls = total

            lead.save(ignore_permissions=True)
        except Exception as e:
            frappe.log_error(f"Failed to update lead call stats: {str(e)}")

    def get_duration_formatted(self):
        """Return duration in MM:SS format"""
        if not self.duration_seconds:
            return "00:00"
        mins = self.duration_seconds // 60
        secs = self.duration_seconds % 60
        return f"{mins:02d}:{secs:02d}"

    def get_status_indicator(self):
        """Get status indicator color for UI"""
        indicators = {
            "initiating": "orange",
            "ringing": "yellow",
            "connected": "blue",
            "ended": "green",
            "failed": "red",
            "no_answer": "gray",
            "missed": "red",
        }
        return indicators.get(self.status, "gray")
