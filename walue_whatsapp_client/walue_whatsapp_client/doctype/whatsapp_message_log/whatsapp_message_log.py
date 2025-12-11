"""
WhatsApp Message Log DocType

Stores ALL message logs LOCALLY in customer's system.

This includes:
- Message content (text, template variables)
- Recipient information
- Status tracking (sent, delivered, read)
- Cost information

IMPORTANT: This data stays in customer's system. Provider only receives
aggregated counts for billing.
"""

import frappe
from frappe.model.document import Document
from datetime import datetime


class WhatsAppMessageLog(Document):
    def before_insert(self):
        """Set defaults before insert"""
        if not self.sent_at:
            self.sent_at = datetime.now()

    def validate(self):
        """Validate message log"""
        # Validate phone number format (basic check)
        if self.to_number and not self.to_number.startswith("+"):
            frappe.msgprint("Phone number should be in E.164 format (e.g., +919876543210)")

    def on_update(self):
        """Update lead on message status change"""
        if self.has_value_changed("status"):
            self._update_lead_stats()

    def _update_lead_stats(self):
        """Update lead's WhatsApp statistics"""
        if not self.lead:
            return

        try:
            lead = frappe.get_doc("CRM Lead", self.lead)

            # Update last message timestamp
            if self.direction == "outbound" and self.status in ["sent", "delivered", "read"]:
                lead.last_whatsapp_message = self.sent_at

            # Count total messages
            total = frappe.db.count("WhatsApp Message Log", {"lead": self.lead})
            lead.total_whatsapp_messages = total

            lead.save(ignore_permissions=True)
        except Exception as e:
            frappe.log_error(f"Failed to update lead stats: {str(e)}")

    def get_status_indicator(self):
        """Get status indicator for UI"""
        indicators = {
            "queued": "orange",
            "sent": "blue",
            "delivered": "green",
            "read": "green",
            "failed": "red",
        }
        return indicators.get(self.status, "gray")
