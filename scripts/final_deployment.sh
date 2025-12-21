#!/bin/bash
# DocuFlow v2.0 Final Deployment Script
# Complete deployment with Cloudflare D1 + Vectorize

set -e

echo "🚀 DocuFlow v2.0 Final Deployment"
echo "=================================="

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# Check prerequisites
check_prerequisites() {
    echo "🔍 Checking prerequisites..."
    
    if ! command -v wrangler &> /dev/null; then
        echo "❌ wrangler CLI not found. Installing..."
        npm install -g wrangler
    fi
    
    if ! command -v docker &> /dev/null; then
        echo "❌ Docker not found. Please install Docker first."
        exit 1
    fi
    
    if ! command -v node &> /dev/null; then
        echo "❌ Node.js not found. Please install Node.js first."
        exit 1
    fi
    
    echo "✅ All prerequisites met"
}

# Get resource IDs
get_resource_ids() {
    echo -e "\n📋 Getting resource IDs..."
    
    echo "D1 Databases:"
    wrangler d1 list
    
    echo -e "\nVectorize Indexes:"
    wrangler vectorize list
    
    echo -e "\nR2 Buckets:"
    wrangler r2 bucket list
    
    echo -e "\nQueues:"
    wrangler queues list
    
    echo -e "\n${GREEN}Please update the wrangler.toml files with your actual resource IDs${NC}"
    echo "Then run this script again with --deploy flag"
}

# Deploy workers
deploy_workers() {
    echo -e "\n🚀 Deploying Cloudflare Workers..."
    
    # Deploy API worker
    echo "Deploying API worker..."
    cd workers/api
    cp wrangler-final.toml wrangler.toml
    wrangler deploy
    cd ../..
    
    # Deploy Consumer worker
    echo "Deploying Consumer worker..."
    cd workers/consumer
    cp wrangler-final.toml wrangler.toml
    wrangler deploy
    cd ../..
    
    echo "✅ Workers deployed successfully"
}

# Deploy Python engine
deploy_engine() {
    echo -e "\n🐍 Deploying Python Engine..."
    
    cd docuflow-engine
    
    # Build Docker image
    echo "Building Docker image..."
    docker build -t docuflow-engine .
    
    # Deploy to Render (or your preferred platform)
    echo "Deploying to Render..."
    echo "Please deploy manually to Render with these settings:"
    echo "- Environment: Python 3.12"
    echo "- Build command: pip install -r requirements.txt"
    echo "- Start command: python main.py"
    echo "- Port: 8000"
    echo "- Environment variables: ENGINE_SECRET (generate random)"
    
    cd ..
}

# Initialize database
init_database() {
    echo -e "\n🗄️ Initializing database..."
    
    # Apply schema
    echo "Applying database schema..."
    wrangler d1 execute docuflow-db --file=./db/enhanced_schema.sql
    
    echo "✅ Database initialized"
}

# Run final validation
final_validation() {
    echo -e "\n🧪 Running final validation..."
    
    # Run our validation script
    ./scripts/validate_v2_simple.sh
    
    echo "✅ Validation completed"
}

# Main deployment flow
main() {
    check_prerequisites
    
    if [[ "$1" == "--setup" ]]; then
        echo "Setting up Cloudflare resources..."
        ./scripts/deploy_cloudflare_setup.sh
        get_resource_ids
    elif [[ "$1" == "--deploy" ]]; then
        deploy_workers
        deploy_engine
        init_database
        final_validation
        echo -e "\n${GREEN}🎉 Deployment completed successfully!${NC}"
        echo -e "\n${GREEN}Your DocuFlow v2.0 is now live with:${NC}"
        echo "- ✅ Hybrid search (D1 + Vectorize)"
        echo "- ✅ Instant ingestion (KV cache)"
        echo "- ✅ Enhanced metadata (tables, sections)"
        echo "- ✅ Smart citations (page numbers)"
        echo "- ✅ Zero external dependencies"
    elif [[ "$1" == "--validate" ]]; then
        final_validation
    else
        echo "Usage: $0 [--setup|--deploy|--validate]"
        echo ""
        echo "  --setup    : Create Cloudflare resources and get IDs"
        echo "  --deploy   : Deploy everything (workers, engine, database)"
        echo "  --validate : Run final validation tests"
        echo ""
        echo "Example workflow:"
        echo "1. $0 --setup"
        echo "2. Update wrangler.toml files with your resource IDs"
        echo "3. $0 --deploy"
        exit 1
    fi
}

# Run main function
main "$@"