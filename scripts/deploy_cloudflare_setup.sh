#!/bin/bash
# DocuFlow v2.0 Cloudflare Deployment Setup
# Exact commands for D1 + Vectorize setup

set -e

echo "🚀 DocuFlow v2.0 Cloudflare Deployment Setup"
echo "=============================================="

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# Check if wrangler is installed
if ! command -v wrangler &> /dev/null; then
    echo "❌ wrangler CLI not found. Installing..."
    npm install -g wrangler
fi

# Login to Cloudflare
echo "🔐 Logging into Cloudflare..."
wrangler login

echo -e "\n${GREEN}1. Creating D1 Database${NC}"
wrangler d1 create docuflow-db

echo -e "\n${GREEN}2. Creating Vectorize Index (768-dim for bge-base-en-v1.5)${NC}"
wrangler vectorize create docuflow-index \
  --dimensions=768 \
  --metric=cosine

echo -e "\n${GREEN}3. Creating R2 Buckets${NC}"
wrangler r2 bucket create docuflow-docs
wrangler r2 bucket create docuflow-metadata

# Set CORS for docs bucket
cat > cors.json << 'EOF'
[
  {
    "AllowedOrigins": ["*"],
    "AllowedMethods": ["GET", "HEAD"],
    "AllowedHeaders": ["*"],
    "MaxAgeSeconds": 3000
  }
]
EOF

wrangler r2 bucket put-cors docuflow-docs --file cors.json
rm cors.json

echo -e "\n${GREEN}4. Creating Queues${NC}"
wrangler queues create docuflow-ingest
wrangler queues create docuflow-events
wrangler queues create docuflow-ingest-dlq
wrangler queues create docuflow-events-dlq

echo -e "\n${GREEN}5. Setup Complete!${NC}"
echo -e "\n${GREEN}Next steps:${NC}"
echo "1. Update wrangler.toml files with your actual IDs"
echo "2. Deploy the workers"
echo "3. Run the validation script"

echo -e "\n${GREEN}To get your resource IDs, run:${NC}"
echo "wrangler d1 list"
echo "wrangler vectorize list"
echo "wrangler r2 bucket list"
echo "wrangler queues list"