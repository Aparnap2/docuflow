# FreightStructurize - Automated Freight Auditor & Compliance Officer

FreightStructurize is an autonomous "Back-Office Agent" for 3PLs and Freight Brokers. It performs forensic auditing on every Bill of Lading (BoL) and Carrier Invoice to:

1. **Recover Revenue:** Catch carrier overcharges (Rate vs. Contract)
2. **Ensure Compliance:** Detect "bad redactions" (text leaks) in sensitive legal/freight docs
3. **Automate Entry:** Sync validated data to TMS (Transportation Management System)

## Architecture

The system consists of multiple Cloudflare Workers and a Python processing engine:

- **Email Worker**: Receives freight documents at `invoices@freightstructurize.ai` and queues processing jobs
- **Engine**: AI-powered PDF processing and freight-specific data extraction
- **Sync Worker**: Processes extracted data, performs freight audits, and updates TMS systems
- **Billing Worker**: Handles subscription management via Lemon Squeezy
- **Pages**: Web dashboard for users to manage their account and view jobs

## Features

- **Freight Invoice Processing**: Forward BoL and carrier invoices to your freight email address → automatic data extraction → TMS integration
- **AI-Powered Extraction**: Advanced language models extract PRO Number, Carrier Name, Origin/Destination ZIPs, Billable Weight, Line Haul Rate, Fuel Surcharge, and Total Amount
- **Rate Auditing**: Validates invoiced amounts against contract rates to detect overcharges
- **Security Auditing**: Scans PDFs for bad redactions where sensitive text exists under black boxes
- **Data Validation & Audit**: Multi-layer validation including rate comparison and redaction detection
- **Subscription Management**: Integrated billing with Lemon Squeezy
- **Demo Flow**: Special handling for demo@structurize.ai to showcase the service
- **Secure Document Processing**: Direct R2 access for document retrieval

## Components

### Email Worker
- Receives emails with PDF attachments at freight-specific addresses
- Stores documents in R2 storage
- Calls processing engine
- Queues jobs for sync processing
- Special handling for demo@structurize.ai

### Processing Engine
- AI-powered PDF parsing and freight data extraction
- Extracts PRO Number, Carrier Name, Origin/Dest ZIPs, Billable Weight, Line Haul Rate, Fuel Surcharge, Total Amount
- Generates visual proof for validation
- Configurable AI model settings

### Sync Worker
- Processes extracted data from jobs queue
- Performs freight-specific audit checks (rate validation, redaction detection)
- Updates TMS systems with validated data
- Stores audit results in audit_jobs table
- Implements retry logic and dead-letter handling
- Sends Slack alerts for flagged audits

### Billing Worker
- Handles Lemon Squeezy webhooks with signature verification
- Manages user subscription plans
- Supports multiple product tiers

### Dashboard (Pages)
- User dashboard to view processing jobs
- Shows job status and audit results
- Displays user subscription information

## Configuration

### Environment Variables

#### Email Worker
- `ENGINE_URL`: URL of the processing engine
- `ENGINE_SECRET`: Secret for authenticating with engine
- `R2_PUBLIC_URL`: Public URL for R2 bucket

#### Sync Worker
- `DEMO_TMS_WEBHOOK_URL`: Webhook URL for demo TMS integration
- `SLACK_WEBHOOK_URL`: Webhook URL for audit alerts
- `DEMO_SHEET_REFRESH_TOKEN`: Refresh token for demo sheet access (fallback)
- `DEMO_SPREADSHEET_ID`: ID of the demo spreadsheet (fallback)
- `EMAIL_SERVICE_URL`: URL for sending notification emails

#### Billing Worker
- `LEMONSQEEZY_SECRET`: Lemon Squeezy API secret
- `LEMON_STARTER_PRODUCT_ID`: Product ID for starter plan
- `LEMON_PRO_PRODUCT_ID`: Product ID for pro plan
- `LEMONSQEEZY_STORE_ID`: Lemon Squeezy store ID

#### Engine
- `ENGINE_SECRET`: Secret for authenticating requests
- `R2_ACCESS_KEY`: R2 access key
- `R2_SECRET_KEY`: R2 secret key
- `R2_ENDPOINT`: R2 endpoint URL
- `R2_PUBLIC_URL`: Public R2 URL
- `LANGEXTRACT_MODEL_ID`: AI model to use (default: gemini-2.5-flash)
- `LANGEXTRACT_PASSES`: Number of extraction passes (default: 2)
- `LANGEXTRACT_MAX_WORKERS`: Max concurrent workers (default: 4)

## Setup & Deployment

See [DEPLOYMENT_COMMANDS.md](DEPLOYMENT_COMMANDS.md) for detailed deployment instructions.

## Security

- Lemon Squeezy webhook signature verification
- API authentication with secrets
- User/org isolation in data access
- Secure R2 document access
- Redaction detection for sensitive document compliance

## Development

The system is designed with microservices architecture for scalability and maintainability. Each component can be developed and deployed independently.

## Database Schema

The system uses PostgreSQL with the following key tables:
- `organizations`: Tenant information for 3PLs and freight brokers
- `rate_cards`: Contract rates for carriers and lanes
- `audit_jobs`: Audit results and status tracking
- `audit_logs`: Detailed audit trail information

## License

[Specify license here]