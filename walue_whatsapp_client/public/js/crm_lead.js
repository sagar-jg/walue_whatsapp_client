/**
 * CRM Lead WhatsApp Integration
 *
 * Adds WhatsApp Call and Message buttons to CRM Lead form
 * Handles WebRTC call interface and message composer
 */

frappe.ui.form.on('CRM Lead', {
    refresh: function(frm) {
        if (!frm.is_new()) {
            add_whatsapp_buttons(frm);
            setup_realtime_listeners(frm);
        }
    },

    onload: function(frm) {
        // Check WhatsApp configuration
        frappe.call({
            method: 'walue_whatsapp_client.api.auth.check_connection',
            callback: function(r) {
                if (!r.message || !r.message.connected) {
                    frm.set_intro(__('WhatsApp not configured. <a href="/app/whatsapp-settings">Configure now</a>'), 'yellow');
                }
            }
        });
    }
});

function add_whatsapp_buttons(frm) {
    // Remove existing buttons first
    frm.remove_custom_button(__('WhatsApp Call'));
    frm.remove_custom_button(__('Send WhatsApp'));

    // Get phone number
    const phone = frm.doc.whatsapp_number || frm.doc.mobile_no;

    if (!phone) {
        return;
    }

    // Add WhatsApp Call button
    frm.add_custom_button(__('WhatsApp Call'), function() {
        initiate_whatsapp_call(frm);
    }, __('WhatsApp'));

    // Add Send Message button
    frm.add_custom_button(__('Send Message'), function() {
        show_message_composer(frm);
    }, __('WhatsApp'));

    // Color the buttons
    frm.change_custom_button_type(__('WhatsApp Call'), 'WhatsApp', 'success');
    frm.change_custom_button_type(__('Send Message'), 'WhatsApp', 'primary');
}

function initiate_whatsapp_call(frm) {
    // First check permission status
    frappe.call({
        method: 'walue_whatsapp_client.api.calls.check_permission',
        args: { lead_id: frm.doc.name },
        callback: function(r) {
            if (!r.message) return;

            const status = r.message;

            if (status.can_call) {
                // Permission granted, initiate call
                start_call(frm);
            } else if (status.can_request) {
                // Need to request permission
                frappe.confirm(
                    status.message + '<br><br>Would you like to send a permission request?',
                    function() {
                        request_call_permission(frm);
                    }
                );
            } else {
                // Cannot call or request
                frappe.msgprint({
                    title: __('Cannot Call'),
                    message: status.message,
                    indicator: 'orange'
                });
            }
        }
    });
}

function request_call_permission(frm) {
    frappe.call({
        method: 'walue_whatsapp_client.api.calls.request_permission',
        args: { lead_id: frm.doc.name },
        freeze: true,
        freeze_message: __('Sending permission request...'),
        callback: function(r) {
            if (r.message && r.message.success) {
                frappe.show_alert({
                    message: __('Permission request sent. You will be notified when approved.'),
                    indicator: 'green'
                });
                frm.reload_doc();
            } else {
                frappe.msgprint({
                    title: __('Error'),
                    message: r.message ? r.message.error : __('Failed to send request'),
                    indicator: 'red'
                });
            }
        }
    });
}

function start_call(frm) {
    frappe.call({
        method: 'walue_whatsapp_client.api.calls.initiate',
        args: { lead_id: frm.doc.name },
        freeze: true,
        freeze_message: __('Connecting call...'),
        callback: function(r) {
            if (r.message && r.message.success) {
                show_call_widget(frm, r.message);
            } else {
                frappe.msgprint({
                    title: __('Call Failed'),
                    message: r.message ? r.message.error : __('Could not initiate call'),
                    indicator: 'red'
                });
            }
        }
    });
}

function show_call_widget(frm, call_data) {
    // Create call widget dialog
    const dialog = new frappe.ui.Dialog({
        title: __('WhatsApp Call'),
        size: 'small',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'call_status',
                options: `
                    <div class="whatsapp-call-widget text-center">
                        <div class="call-avatar mb-3">
                            <i class="fa fa-user-circle fa-5x text-muted"></i>
                        </div>
                        <h4>${frm.doc.lead_name || frm.doc.name}</h4>
                        <p class="text-muted">${frm.doc.whatsapp_number || frm.doc.mobile_no}</p>
                        <div class="call-status mt-3">
                            <span class="badge badge-info" id="call-status-badge">Connecting...</span>
                        </div>
                        <div class="call-timer mt-2" id="call-timer" style="display:none;">
                            <h3 id="timer-display">00:00</h3>
                        </div>
                    </div>
                `
            },
            {
                fieldtype: 'Small Text',
                fieldname: 'call_notes',
                label: __('Notes'),
            }
        ],
        primary_action_label: __('End Call'),
        primary_action: function() {
            end_call(frm, call_data.call_log_id, dialog);
        }
    });

    dialog.show();
    dialog.$wrapper.find('.btn-primary').addClass('btn-danger').removeClass('btn-primary');

    // Initialize WebRTC connection
    initialize_webrtc(call_data, dialog);
}

function initialize_webrtc(call_data, dialog) {
    // This would connect to Janus WebRTC gateway
    // Simplified for now - actual implementation needs Janus JS library

    const statusBadge = dialog.$wrapper.find('#call-status-badge');
    const timer = dialog.$wrapper.find('#call-timer');
    const timerDisplay = dialog.$wrapper.find('#timer-display');

    // Simulate connection states
    setTimeout(() => {
        statusBadge.text('Ringing...').removeClass('badge-info').addClass('badge-warning');
    }, 1000);

    setTimeout(() => {
        statusBadge.text('Connected').removeClass('badge-warning').addClass('badge-success');
        timer.show();
        startTimer(timerDisplay);
    }, 3000);
}

let timerInterval;
let callSeconds = 0;

function startTimer(display) {
    callSeconds = 0;
    timerInterval = setInterval(() => {
        callSeconds++;
        const mins = Math.floor(callSeconds / 60).toString().padStart(2, '0');
        const secs = (callSeconds % 60).toString().padStart(2, '0');
        display.text(`${mins}:${secs}`);
    }, 1000);
}

function end_call(frm, call_log_id, dialog) {
    clearInterval(timerInterval);

    const notes = dialog.get_value('call_notes');

    frappe.call({
        method: 'walue_whatsapp_client.api.calls.end',
        args: {
            call_log_id: call_log_id,
            notes: notes
        },
        callback: function(r) {
            dialog.hide();

            if (r.message && r.message.success) {
                const duration = r.message.duration_seconds;
                const mins = Math.floor(duration / 60);
                const secs = duration % 60;

                frappe.show_alert({
                    message: __('Call ended. Duration: {0}m {1}s', [mins, secs]),
                    indicator: 'green'
                });

                frm.reload_doc();
            }
        }
    });
}

function show_message_composer(frm) {
    // Check conversation window status
    frappe.call({
        method: 'walue_whatsapp_client.api.messages.check_conversation_window',
        args: { lead_id: frm.doc.name },
        callback: function(r) {
            const window_status = r.message || {};
            create_message_dialog(frm, window_status);
        }
    });
}

function create_message_dialog(frm, window_status) {
    // Get templates
    frappe.call({
        method: 'walue_whatsapp_client.api.messages.get_templates',
        callback: function(r) {
            // Handle both old format (array) and new format (object with templates)
            let templates = [];
            if (r.message) {
                if (Array.isArray(r.message)) {
                    templates = r.message;
                } else if (r.message.success && r.message.templates) {
                    templates = r.message.templates;
                }
            }

            const fields = [
                {
                    fieldtype: 'Select',
                    fieldname: 'message_type',
                    label: __('Message Type'),
                    options: window_status.in_window
                        ? 'Template\nText Message'
                        : 'Template',
                    default: 'Template',
                    onchange: function() {
                        const type = dialog.get_value('message_type');
                        dialog.set_df_property('template_name', 'hidden', type !== 'Template');
                        dialog.set_df_property('text_message', 'hidden', type !== 'Text Message');
                    }
                },
                {
                    fieldtype: 'HTML',
                    fieldname: 'template_header',
                    options: `<div class="template-header d-flex align-items-center justify-content-between mb-2">
                        <label class="control-label">${__('Template')}</label>
                        <button type="button" class="btn btn-xs btn-default sync-templates-btn" title="${__('Sync Templates')}">
                            <i class="fa fa-refresh"></i>
                        </button>
                    </div>`
                },
                {
                    fieldtype: 'Select',
                    fieldname: 'template_name',
                    options: templates.map(t => t.template_name).join('\n'),
                },
                {
                    fieldtype: 'Small Text',
                    fieldname: 'text_message',
                    label: __('Message'),
                    hidden: 1,
                }
            ];

            if (!window_status.in_window) {
                fields.unshift({
                    fieldtype: 'HTML',
                    options: `<div class="alert alert-info">
                        <i class="fa fa-info-circle"></i>
                        You can only send template messages. Send a template to start a conversation.
                    </div>`
                });
            }

            const dialog = new frappe.ui.Dialog({
                title: __('Send WhatsApp Message'),
                fields: fields,
                primary_action_label: __('Send'),
                primary_action: function() {
                    send_message(frm, dialog);
                }
            });

            dialog.show();

            // Add sync button click handler
            dialog.$wrapper.find('.sync-templates-btn').on('click', function() {
                const $btn = $(this);
                const $icon = $btn.find('i');

                // Add spinning animation
                $icon.addClass('fa-spin');
                $btn.prop('disabled', true);

                frappe.call({
                    method: 'walue_whatsapp_client.api.messages.sync_templates',
                    callback: function(r) {
                        $icon.removeClass('fa-spin');
                        $btn.prop('disabled', false);

                        if (r.message && r.message.success) {
                            frappe.show_alert({
                                message: __('Synced {0} templates', [r.message.synced_count]),
                                indicator: 'green'
                            });

                            // Refresh template options
                            frappe.call({
                                method: 'walue_whatsapp_client.api.messages.get_templates',
                                callback: function(r2) {
                                    let newTemplates = [];
                                    if (r2.message && r2.message.templates) {
                                        newTemplates = r2.message.templates;
                                    }
                                    const options = newTemplates.map(t => t.template_name).join('\n');
                                    dialog.set_df_property('template_name', 'options', options);
                                }
                            });
                        } else {
                            frappe.show_alert({
                                message: r.message ? r.message.error : __('Sync failed'),
                                indicator: 'red'
                            });
                        }
                    }
                });
            });
        }
    });
}

function send_message(frm, dialog) {
    const message_type = dialog.get_value('message_type');

    if (message_type === 'Template') {
        const template_name = dialog.get_value('template_name');

        if (!template_name) {
            frappe.msgprint(__('Please select a template'));
            return;
        }

        frappe.call({
            method: 'walue_whatsapp_client.api.messages.send_template',
            args: {
                lead_id: frm.doc.name,
                template_name: template_name
            },
            freeze: true,
            freeze_message: __('Sending message...'),
            callback: function(r) {
                dialog.hide();
                handle_send_response(frm, r);
            }
        });
    } else {
        const text = dialog.get_value('text_message');

        if (!text) {
            frappe.msgprint(__('Please enter a message'));
            return;
        }

        frappe.call({
            method: 'walue_whatsapp_client.api.messages.send_text',
            args: {
                lead_id: frm.doc.name,
                text: text
            },
            freeze: true,
            freeze_message: __('Sending message...'),
            callback: function(r) {
                dialog.hide();
                handle_send_response(frm, r);
            }
        });
    }
}

function handle_send_response(frm, response) {
    if (response.message && response.message.success) {
        frappe.show_alert({
            message: __('Message sent successfully'),
            indicator: 'green'
        });
        frm.reload_doc();
    } else {
        frappe.msgprint({
            title: __('Failed'),
            message: response.message ? response.message.error : __('Could not send message'),
            indicator: 'red'
        });
    }
}

function setup_realtime_listeners(frm) {
    // Listen for permission updates
    frappe.realtime.on('whatsapp_permission_update', function(data) {
        if (data.lead === frm.doc.name) {
            frappe.show_alert({
                message: data.can_call
                    ? __('Call permission granted! You can now call this lead.')
                    : __('Call permission status updated'),
                indicator: data.can_call ? 'green' : 'orange'
            });
            frm.reload_doc();
        }
    });

    // Listen for new inbound messages
    frappe.realtime.on('whatsapp_new_message', function(data) {
        if (data.lead === frm.doc.name) {
            frappe.show_alert({
                message: __('New WhatsApp message received'),
                indicator: 'blue'
            });
            frm.reload_doc();
        }
    });

    // Listen for message status updates
    frappe.realtime.on('whatsapp_message_status', function(data) {
        if (data.lead === frm.doc.name) {
            // Could update UI to show read receipts
        }
    });
}
