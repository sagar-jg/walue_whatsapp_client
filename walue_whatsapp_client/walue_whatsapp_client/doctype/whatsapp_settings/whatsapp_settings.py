"""
WhatsApp Settings - Single DocType

Local configuration for WhatsApp integration.
Stores WABA credentials and provider connection details.

IMPORTANT: All WhatsApp credentials are stored HERE in customer's system,
not on the provider platform.
"""

import frappe
from frappe.model.document import Document


class WhatsAppSettings(Document):
    def validate(self):
        """Validate settings"""
        if self.provider_url:
            # Remove trailing slash
            self.provider_url = self.provider_url.rstrip("/")

            # Validate URL format
            if not self.provider_url.startswith(("http://", "https://")):
                frappe.throw("Provider URL must start with http:// or https://")

    def on_update(self):
        """Clear cache on settings update"""
        frappe.cache().delete_value("whatsapp_settings")

    def is_configured(self):
        """Check if WhatsApp is fully configured"""
        return bool(
            self.provider_url and
            self.provider_access_token and
            self.meta_waba_id and
            self.meta_phone_number_id and
            self.meta_access_token
        )

    def is_provider_connected(self):
        """Check if connected to provider"""
        return bool(self.provider_access_token)

    def is_waba_configured(self):
        """Check if WABA is configured"""
        return bool(
            self.meta_waba_id and
            self.meta_phone_number_id and
            self.meta_access_token
        )

    def get_api_headers(self):
        """Get headers for Meta API calls"""
        if not self.meta_access_token:
            frappe.throw("Meta access token not configured")

        return {
            "Authorization": f"Bearer {self.get_password('meta_access_token')}",
            "Content-Type": "application/json",
        }
