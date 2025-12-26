# Sarah AI - Apify Integration

This repository contains the implementation of Sarah AI with Apify integration, transforming the original ParseFlow.ai system into a configurable digital intern for document processing.

## Architecture Overview

### Hybrid Architecture (Cloudflare + Apify)
- **Cloudflare Workers**: Handle email ingestion, user management, and dashboard
- **Apify Actors**: Handle the AI processing with DeepSeek OCR and LangGraph validation
- **Cloudflare D1**: Database for users, blueprints, and jobs
- **Cloudflare R2**: Document storage with presigned URLs for Apify access

### Flow
1. Email arrives at `user@sarah.ai` → Cloudflare Email Worker
2. Email parsed, PDF attachment saved to R2 → Generate presigned URL
3. Trigger Apify Actor with presigned URL and user schema
4. Apify Actor processes document using DeepSeek OCR + LangGraph validation
5. Apify sends results via webhook → Cloudflare Worker updates job
6. Results available in dashboard, can be synced to Google Sheets

## Components

### Apify Actor (`apify/actor.py`)
- Stateful processing with LangGraph
- Schema-based extraction using Pydantic models
- Self-validation and correction capabilities
- Input: PDF URL + extraction schema
- Output: Structured data with validation status

### Cloudflare Workers
- **Email Worker**: Processes incoming emails, triggers Apify
- **Sync Worker**: Handles Apify webhooks, updates job status
- **API Worker**: Provides dashboard API endpoints

### Database Schema
- `users`: Stores user information and OAuth details
- `blueprints`: Custom extraction schemas defined by users
- `jobs`: Processing jobs with status and results
- `apify_webhooks`: Track Apify webhook events for debugging

## Setup

### Prerequisites
- Cloudflare account with Workers, D1, R2
- Apify account with actor access
- Ollama with DeepSeek OCR and IBM Granite Docling models

### Environment Variables
```bash
# Apify
APIFY_TOKEN=your_apify_token
APIFY_ACTOR_ID=your_actor_id

# Cloudflare
CF_ACCOUNT_ID=your_account_id
R2_ACCESS_KEY_ID=your_r2_key
R2_SECRET_ACCESS_KEY=your_r2_secret
WORKER_API_SECRET=your_worker_secret

# Ollama (for local processing during development)
OLLAMA_ENDPOINT=http://localhost:11434
```

### Deployment

1. **Deploy Apify Actor**:
   ```bash
   cd apify
   npm install -g apify-cli
   apify login
   apify push
   ```

2. **Deploy Cloudflare Workers**:
   ```bash
   # Setup D1 database
   wrangler d1 create sarah-ai-db
   wrangler d1 execute sarah-ai-db --file=db/schema.sql
   
   # Setup R2 bucket
   wrangler r2 bucket create sarah-ai-storage
   
   # Deploy workers
   cd pages && wrangler deploy
   cd ../workers/email && wrangler deploy
   cd ../sync && wrangler deploy
   cd ../billing && wrangler deploy
   ```

## Key Features

### 1. Schema-Based Extraction
Users define custom extraction schemas:
```json
[
  {"name": "Vendor", "type": "text", "instruction": "Extract vendor name"},
  {"name": "Total", "type": "currency", "instruction": "Extract total amount"},
  {"name": "Invoice Date", "type": "date", "instruction": "Extract invoice date"}
]
```

### 2. Self-Validating Processing
- LangGraph workflow validates extracted data
- Math validation (e.g., checking if line items sum to total)
- Confidence scoring for each extracted field
- Automatic review requests for low-confidence extractions

### 3. Apify Integration Benefits
- **Cost-Effective**: Apify handles GPU costs
- **Scalable**: Auto-scales based on demand
- **Maintained**: No need to manage OCR infrastructure
- **Standardized**: Strict Pydantic output models

### 4. Hybrid Distribution
- **SaaS**: Monthly subscriptions for agencies
- **Apify Actor**: Usage-based pricing for developers
- **Dual Revenue**: Maximize market reach

## API Endpoints

### Trigger Processing
```bash
POST /process-with-apify
{
  "pdf_url": "https://example.com/invoice.pdf",
  "schema": [...],
  "job_id": "optional_existing_job_id"
}
```

### Webhook for Apify Results
```bash
POST /webhook/apify-result
```

### Job Status
```bash
GET /jobs/{job_id}
```

## Development

### Running Locally
```bash
# Install dependencies
pip install -r apify/requirements.txt

# Run tests
python -m pytest apify/test_apify_integration.py

# Start local processing (for development)
cd engine
uvicorn main:app --reload
```

### Testing the Actor
The actor can be tested locally using the Apify CLI:
```bash
apify run
```

## Migration from Modal

### What Changed
- **Before**: Cloudflare → Modal (Python AI) → Results
- **After**: Cloudflare → Apify Actor (Python AI) → Results

### Migration Steps
1. Replaced Modal function calls with Apify API calls
2. Updated database schema to track Apify run IDs
3. Added webhook handling for Apify results
4. Maintained same API endpoints for backward compatibility

## Benefits of Apify Architecture

1. **Cost Reduction**: Apify pays for GPU usage
2. **Simplified Infrastructure**: No Modal container management
3. **Better Scaling**: Apify auto-scales processing
4. **Dual Revenue Model**: SaaS + Apify Actor marketplace
5. **Enhanced Validation**: Stateful LangGraph workflows

## Future Enhancements

- Advanced validation workflows with human-in-the-loop
- More sophisticated schema templates
- Enhanced dashboard with processing analytics
- Integration with more business applications (not just Google Sheets)

## License

MIT