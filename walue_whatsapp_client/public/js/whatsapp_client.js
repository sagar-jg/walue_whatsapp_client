/**
 * Walue WhatsApp Client - Main JS
 *
 * Global utilities and initialization
 */

// Namespace
frappe.provide('walue_whatsapp');

walue_whatsapp = {
    // Check if WhatsApp is configured
    is_configured: false,

    init: function() {
        // Check configuration on load
        frappe.call({
            method: 'walue_whatsapp_client.api.auth.check_connection',
            async: false,
            callback: function(r) {
                if (r.message) {
                    walue_whatsapp.is_configured = r.message.connected && r.message.waba_configured;
                }
            }
        });
    },

    // Format phone number for display
    format_phone: function(phone) {
        if (!phone) return '';
        // Basic formatting - actual implementation should use libphonenumber
        return phone;
    },

    // Format duration in seconds to MM:SS
    format_duration: function(seconds) {
        if (!seconds) return '00:00';
        const mins = Math.floor(seconds / 60).toString().padStart(2, '0');
        const secs = (seconds % 60).toString().padStart(2, '0');
        return `${mins}:${secs}`;
    },

    // Get status badge HTML
    get_status_badge: function(status) {
        const badges = {
            'sent': '<span class="badge badge-info">Sent</span>',
            'delivered': '<span class="badge badge-success">Delivered</span>',
            'read': '<span class="badge badge-primary">Read</span>',
            'failed': '<span class="badge badge-danger">Failed</span>',
            'queued': '<span class="badge badge-secondary">Queued</span>',
            'granted': '<span class="badge badge-success">Granted</span>',
            'requested': '<span class="badge badge-warning">Pending</span>',
            'expired': '<span class="badge badge-secondary">Expired</span>',
            'none': '<span class="badge badge-light">None</span>',
        };
        return badges[status] || `<span class="badge badge-light">${status}</span>`;
    }
};

// Initialize on page load
$(document).ready(function() {
    walue_whatsapp.init();
});
