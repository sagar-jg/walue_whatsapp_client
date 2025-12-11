# Walue WhatsApp Client

WhatsApp Calling & Messaging Client for Frappe/ERPNext CRM.

## Overview

This is the **customer-side** Frappe app that integrates WhatsApp capabilities into your CRM. It provides:

- WhatsApp Call button on CRM Leads
- WhatsApp Message button on CRM Leads
- Local storage of all call and message logs
- Template message management
- Call permission tracking

## Installation

```bash
bench get-app https://github.com/sagar-jg/walue_whatsapp_client.git
bench --site your-site install-app walue_whatsapp_client
```

## Configuration

1. Go to **WhatsApp Settings**
2. Enter provider URL and OAuth credentials
3. Complete embedded signup or manually configure WABA
4. Sync templates

## DocTypes

| DocType | Purpose |
|---------|---------|
| WhatsApp Settings | Configuration & credentials |
| WhatsApp Message Log | All message history (local) |
| WhatsApp Call Log | All call history (local) |
| WhatsApp Template | Cached message templates |
| WhatsApp Call Permission | Permission tracking per lead |

## CRM Integration

After installation, CRM Lead forms will have:
- **WhatsApp Call** button - Initiate voice calls
- **Send WhatsApp** button - Send template or text messages

## Data Ownership

All your data stays in YOUR system:
- Message content stored locally
- Call recordings stored locally
- Phone numbers stay in your database
- Only aggregated counts sent to provider for billing

## License

MIT
