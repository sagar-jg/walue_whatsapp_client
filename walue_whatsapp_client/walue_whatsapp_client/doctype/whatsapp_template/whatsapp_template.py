"""
WhatsApp Template DocType

Local cache of approved message templates from WABA.
Synced periodically from Meta API.
"""

import frappe
from frappe.model.document import Document
import json


class WhatsAppTemplate(Document):
    def get_components(self):
        """Return components as parsed JSON"""
        if self.components:
            return json.loads(self.components)
        return []

    def get_body_text(self):
        """Extract body text from components"""
        components = self.get_components()
        for comp in components:
            if comp.get("type") == "BODY":
                return comp.get("text", "")
        return ""

    def get_variable_count(self):
        """Count variables in template body"""
        import re
        body = self.get_body_text()
        # Match {{1}}, {{2}}, etc.
        variables = re.findall(r"\{\{\d+\}\}", body)
        return len(variables)

    def is_approved(self):
        """Check if template is approved"""
        return self.status == "approved"
