# Docuflow Deployment Guide

This document outlines the deployment process for the Docuflow application, which consists of:
- Hono web application (Cloudflare Workers)
- Email ingestion worker (Cloudflare Worker)
- Queue consumer worker (Cloudflare Worker)
- Python AI engine (Docker container)

## Prerequisites

- Node.js 18+ and pnpm
- Docker and Docker Compose
- Cloudflare account with Workers enabled
- Python 3.11+
- Access to a PostgreSQL database

## Environment Variables

### Web Application & Workers

Create a `.env.production` file with the following variables:

```bash
# Database
DATABASE_URL="postgresql://username:password@host:port/database"
DIRECT_URL="postgresql://username:password@host:port/database"

# Auth
AUTH_SECRET="your-very-secret-auth-key"
AUTH_BASE_URL="https://yourdomain.com"

# Google OAuth
GOOGLE_CLIENT_ID="your-google-client-id"
GOOGLE_CLIENT_SECRET="your-google-client-secret"

# Frontend URL
FRONTEND_URL="https://yourdomain.com"

# Discord Webhook (optional)
DISCORD_WEBHOOK_URL="your-discord-webhook-url"

# HubSpot API (optional)
HUBSPOT_API_KEY="your-hubspot-api-key"

# Lemon Squeezy (optional)
LEMON_SQUEEZY_WEBHOOK_SECRET="your-lemon-squeezy-webhook-secret"

# Python Engine
PYTHON_ENGINE_URL="https://your-python-engine.com/process"
PYTHON_ENGINE_SECRET="your-python-engine-secret"
```

### Python Engine

Create a `.env` file in the `docuflow-engine` directory:

```bash
# Engine configuration
ENGINE_SECRET="your-engine-secret"
WEBHOOK_SECRET="your-webhook-secret"

# Ollama configuration
OLLAMA_BASE_URL="http://localhost:11434/v1"

# Google Drive configuration
GOOGLE_CREDENTIALS_FILE="path-to-credentials.json"
GOOGLE_TOKEN_FILE="token.pickle"

# Logging
LOG_LEVEL="INFO"
```

## Deployment Steps

### 1. Deploy Workers to Cloudflare

#### Deploy the web application (Hono app):

```bash
cd apps/web
pnpm install
pnpm run build
pnpm run deploy
```

#### Deploy the email ingestion worker:

```bash
cd workers/email-ingest
pnpm install
pnpm run deploy
```

#### Deploy the queue consumer worker:

```bash
cd workers/queue-consumer
pnpm install
pnpm run deploy
```

### 2. Deploy Python Engine

#### Build and deploy the Docker container:

```bash
cd docuflow-engine
docker build -t docuflow-engine .
docker tag docuflow-engine your-registry/docuflow-engine:latest
docker push your-registry/docuflow-engine:latest
```

### 3. Setup Database

#### Run Prisma migrations:

```bash
cd packages/database
npx prisma migrate deploy
```

### 4. Setup Cloudflare Resources

#### R2 Bucket:
Create an R2 bucket named `docuflow-documents`:
```bash
wrangler r2 bucket create docuflow-documents
```

#### Queues:
Create the required queues via Cloudflare Dashboard or API:
- `document-processing-queue`
- `document-processing-dlq`

### 5. Configure Environment Variables in Cloudflare

Use Wrangler to configure environment variables for your workers:

```bash
wrangler secret put DATABASE_URL --name email-ingest
wrangler secret put AUTH_SECRET --name email-ingest
# ... repeat for all required secrets
```

## Running Locally for Development

### 1. Install dependencies:

```bash
pnpm install
```

### 2. Start the web application with Wrangler:

```bash
cd apps/web
pnpm run dev
```

### 3. Start the Python engine:

```bash
cd docuflow-engine
pip install -r requirements.txt
uvicorn main:app --reload
```

## Observability and Monitoring

### Logging

- Web and Workers: Loguru with structured JSON logging
- Python Engine: Loguru with file and console output
- All logs are stored in `logs/` directory

### Health Checks

- Web app: `GET /health`
- Workers: Built-in Cloudflare observability
- Python engine: `GET /health`

### Error Tracking

- All services implement structured error logging
- Failed queue messages are sent to Dead Letter Queue
- Webhook failures are logged with detailed error information

## Troubleshooting

### Common Issues

1. **Worker deployment fails**: Check that all environment variables are set correctly
2. **Database connection issues**: Verify DATABASE_URL format and network access
3. **Python engine timeouts**: Ensure Ollama service is running and accessible
4. **Auth failures**: Check AUTH_SECRET consistency across services

### Monitoring

- Cloudflare Workers dashboard for worker metrics
- PostgreSQL logs for database performance
- Python engine logs for processing metrics
- Queue depth monitoring through Cloudflare dashboard

## Rollback Procedure

1. Use Cloudflare's deployment history to rollback Workers
2. Use Docker image tags to rollback Python engine
3. Run database rollback migrations if needed