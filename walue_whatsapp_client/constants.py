"""
Constants for Walue WhatsApp Client App
All business rules, UI messages, and status values
"""

# =============================================================================
# META API BUSINESS RULES (Same as provider)
# =============================================================================

# Call Permission Request Limits
CALL_PERMISSION_DAILY_LIMIT = 1  # Max permission requests per 24 hours
CALL_PERMISSION_WEEKLY_LIMIT = 2  # Max permission requests per 7 days
MAX_CALLS_AFTER_PERMISSION = 5  # Max calls per 24 hours after permission granted
PERMISSION_VALIDITY_DAYS = 7  # Permission expires after 7 days

# Conversation Windows
CONVERSATION_WINDOW_HOURS = 24  # Free messaging window after user message

# =============================================================================
# UI MESSAGES - CALL
# =============================================================================

MSG_CONNECTING = "Connecting to WhatsApp..."
MSG_CALL_RINGING = "Ringing..."
MSG_CALL_CONNECTED = "Call connected"
MSG_CALL_ENDED = "Call ended"
MSG_CALL_FAILED = "Call could not be connected"

# =============================================================================
# UI MESSAGES - MESSAGE
# =============================================================================

MSG_MESSAGE_SENDING = "Sending message..."
MSG_MESSAGE_SENT = "Message sent successfully"
MSG_MESSAGE_DELIVERED = "Delivered"
MSG_MESSAGE_READ = "Read"
MSG_MESSAGE_FAILED = "Message failed to send"

# =============================================================================
# UI MESSAGES - PERMISSION
# =============================================================================

MSG_PERMISSION_REQUIRED = "Call permission required. Send request to customer?"
MSG_PERMISSION_PENDING = "Permission request sent. Awaiting customer approval."
MSG_PERMISSION_GRANTED = "Call permission granted. You can now call this customer."
MSG_PERMISSION_EXPIRED = "Call permission expired. Send new request?"
MSG_DAILY_LIMIT = "Daily permission request limit reached. Try again tomorrow."
MSG_WEEKLY_LIMIT = "Weekly permission request limit reached (2 requests per 7 days)."
MSG_CALL_LIMIT = "Daily call limit reached (5 calls per permission)."

# =============================================================================
# ERROR MESSAGES
# =============================================================================

ERR_NO_PERMISSION = "No call permission. Please request permission first."
ERR_INVALID_PHONE = "Invalid WhatsApp phone number format. Use E.164 format (e.g., +919876543210)"
ERR_CALL_FAILED = "Call could not be initiated. Please try again."
ERR_MESSAGE_FAILED = "Message could not be sent. Please check status."
ERR_OUTSIDE_WINDOW = "Cannot send free-form message. Use template or wait for customer response."
ERR_TEMPLATE_NOT_FOUND = "Selected template not found or not approved."
ERR_NOT_CONFIGURED = "WhatsApp not configured. Please complete setup in Settings."
ERR_NOT_CONNECTED = "Not connected to Walue platform. Please reconnect."
ERR_PROVIDER_ERROR = "Provider error. Please try again or contact support."

# =============================================================================
# TEMPLATE CATEGORIES
# =============================================================================

TEMPLATE_CATEGORY_MARKETING = "marketing"
TEMPLATE_CATEGORY_UTILITY = "utility"
TEMPLATE_CATEGORY_AUTHENTICATION = "authentication"
TEMPLATE_CATEGORY_SERVICE = "service"

TEMPLATE_CATEGORIES = [
    {"value": TEMPLATE_CATEGORY_MARKETING, "label": "Marketing"},
    {"value": TEMPLATE_CATEGORY_UTILITY, "label": "Utility"},
    {"value": TEMPLATE_CATEGORY_AUTHENTICATION, "label": "Authentication"},
    {"value": TEMPLATE_CATEGORY_SERVICE, "label": "Service"},
]

# =============================================================================
# CALL STATUS
# =============================================================================

CALL_STATUS_INITIATING = "initiating"
CALL_STATUS_RINGING = "ringing"
CALL_STATUS_CONNECTED = "connected"
CALL_STATUS_ENDED = "ended"
CALL_STATUS_FAILED = "failed"
CALL_STATUS_NO_ANSWER = "no_answer"
CALL_STATUS_MISSED = "missed"

CALL_STATUS_OPTIONS = [
    {"value": CALL_STATUS_INITIATING, "label": "Initiating"},
    {"value": CALL_STATUS_RINGING, "label": "Ringing"},
    {"value": CALL_STATUS_CONNECTED, "label": "Connected"},
    {"value": CALL_STATUS_ENDED, "label": "Completed"},
    {"value": CALL_STATUS_FAILED, "label": "Failed"},
    {"value": CALL_STATUS_NO_ANSWER, "label": "No Answer"},
    {"value": CALL_STATUS_MISSED, "label": "Missed"},
]

# =============================================================================
# MESSAGE STATUS
# =============================================================================

MESSAGE_STATUS_QUEUED = "queued"
MESSAGE_STATUS_SENT = "sent"
MESSAGE_STATUS_DELIVERED = "delivered"
MESSAGE_STATUS_READ = "read"
MESSAGE_STATUS_FAILED = "failed"

MESSAGE_STATUS_OPTIONS = [
    {"value": MESSAGE_STATUS_QUEUED, "label": "Queued"},
    {"value": MESSAGE_STATUS_SENT, "label": "Sent"},
    {"value": MESSAGE_STATUS_DELIVERED, "label": "Delivered"},
    {"value": MESSAGE_STATUS_READ, "label": "Read"},
    {"value": MESSAGE_STATUS_FAILED, "label": "Failed"},
]

# =============================================================================
# PERMISSION STATUS
# =============================================================================

PERMISSION_STATUS_NONE = "none"
PERMISSION_STATUS_REQUESTED = "requested"
PERMISSION_STATUS_GRANTED = "granted"
PERMISSION_STATUS_EXPIRED = "expired"
PERMISSION_STATUS_REVOKED = "revoked"

PERMISSION_STATUS_OPTIONS = [
    {"value": PERMISSION_STATUS_NONE, "label": "None"},
    {"value": PERMISSION_STATUS_REQUESTED, "label": "Requested"},
    {"value": PERMISSION_STATUS_GRANTED, "label": "Granted"},
    {"value": PERMISSION_STATUS_EXPIRED, "label": "Expired"},
    {"value": PERMISSION_STATUS_REVOKED, "label": "Revoked"},
]

# =============================================================================
# MESSAGE DIRECTION
# =============================================================================

DIRECTION_INBOUND = "inbound"
DIRECTION_OUTBOUND = "outbound"

# =============================================================================
# MESSAGE TYPES
# =============================================================================

MESSAGE_TYPE_TEMPLATE = "template"
MESSAGE_TYPE_TEXT = "text"
MESSAGE_TYPE_MEDIA = "media"

# =============================================================================
# CALL DIRECTION
# =============================================================================

CALL_DIRECTION_INBOUND = "inbound"
CALL_DIRECTION_OUTBOUND = "outbound"

# =============================================================================
# PHONE NUMBER VALIDATION
# =============================================================================

# E.164 format: + followed by country code and number (max 15 digits)
PHONE_REGEX = r"^\+[1-9]\d{1,14}$"

# =============================================================================
# WEBRTC CONFIGURATION
# =============================================================================

WEBRTC_ICE_GATHERING_TIMEOUT = 10000  # 10 seconds
WEBRTC_CONNECTION_TIMEOUT = 30000  # 30 seconds

# =============================================================================
# SYNC INTERVALS
# =============================================================================

MESSAGE_STATUS_POLL_INTERVAL = 300  # 5 minutes (in seconds)
TEMPLATE_SYNC_INTERVAL = 3600  # 1 hour (in seconds)
USAGE_REPORT_INTERVAL = 3600  # 1 hour (in seconds)
