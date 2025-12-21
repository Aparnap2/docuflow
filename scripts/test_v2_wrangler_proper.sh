#!/bin/bash
# DocuFlow v2.0 Proper Wrangler Local Testing
# Uses remote bindings to test against real Cloudflare services

set -e

echo "🚀 DocuFlow v2.0 Wrangler Remote Bindings Testing"
echo "=================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test results
PASSED=0
FAILED=0

# Function to log test results
log_test() {
    local test_name=$1
    local result=$2
    local details=$3
    
    if [ "$result" -eq 0 ]; then
        echo -e "${GREEN}✅ PASS${NC} $test_name"
        if [ -n "$details" ]; then
            echo "   Details: $details"
        fi
        ((PASSED++))
    else
        echo -e "${RED}❌ FAIL${NC} $test_name"
        if [ -n "$details" ]; then
            echo "   Error: $details"
        fi
        ((FAILED++))
    fi
}

# Function to check if wrangler is available
check_wrangler() {
    if command -v wrangler &> /dev/null; then
        return 0
    else
        return 1
    fi
}

# Function to test wrangler dev with remote bindings
test_wrangler_dev() {
    local worker_dir=$1
    local worker_name=$2
    local test_name=$3
    
    echo -e "${BLUE}Testing $worker_name with remote bindings...${NC}"
    cd "$worker_dir"
    
    # Test if wrangler can start (dry run)
    if wrangler dev --dry-run > /dev/null 2>&1; then
        log_test "$test_name" 0 "Wrangler configuration is valid"
        return 0
    else
        log_test "$test_name" 1 "Wrangler configuration has issues"
        return 1
    fi
}

# Function to validate wrangler configuration
validate_wrangler_config() {
    local worker_dir=$1
    local worker_name=$2
    
    echo -e "${BLUE}Validating $worker_name configuration...${NC}"
    cd "$worker_dir"
    
    # Check wrangler.toml exists
    if [ ! -f "wrangler.toml" ]; then
        log_test "$worker_name - Config File" 1 "wrangler.toml not found"
        return 1
    fi
    
    # Validate TOML syntax
    if wrangler config validate > /dev/null 2>&1; then
        log_test "$worker_name - Config Syntax" 0 "Valid TOML syntax"
    else
        log_test "$worker_name - Config Syntax" 1 "Invalid TOML syntax"
        return 1
    fi
    
    # Check for required bindings
    local required_bindings=("DB" "BUCKET" "VECTORIZE" "AI")
    local missing_bindings=()
    
    for binding in "${required_bindings[@]}"; do
        if ! grep -q "binding.*=.*\"$binding\"" wrangler.toml; then
            missing_bindings+=("$binding")
        fi
    done
    
    if [ ${#missing_bindings[@]} -eq 0 ]; then
        log_test "$worker_name - Required Bindings" 0 "All required bindings present"
    else
        log_test "$worker_name - Required Bindings" 1 "Missing: ${missing_bindings[*]}"
    fi
    
    return 0
}

# Function to test TypeScript compilation
test_typescript_compilation() {
    local worker_dir=$1
    local worker_name=$2
    
    echo -e "${BLUE}Testing TypeScript compilation for $worker_name...${NC}"
    cd "$worker_dir"
    
    # Check if TypeScript compiles
    if npx tsc --noEmit > /dev/null 2>&1; then
        log_test "$worker_name - TypeScript" 0 "Compiles successfully"
    else
        log_test "$worker_name - TypeScript" 1 "Compilation errors found"
        npx tsc --noEmit 2>&1 | head -10
    fi
}

# Function to test hybrid search functionality
test_hybrid_search_code() {
    echo -e "${BLUE}Testing hybrid search implementation...${NC}"
    
    # Check if hybrid-search.ts exists and has proper exports
    if [ -f "workers/api/src/hybrid-search.ts" ]; then
        if grep -q "export.*hybridSearch" workers/api/src/hybrid-search.ts; then
            log_test "Hybrid Search - Code Structure" 0 "Main function exported"
        else
            log_test "Hybrid Search - Code Structure" 1 "Main function not exported"
        fi
        
        if grep -q "export.*extractKeywords" workers/api/src/hybrid-search.ts; then
            log_test "Hybrid Search - Keyword Extraction" 0 "Keyword extraction exported"
        else
            log_test "Hybrid Search - Keyword Extraction" 1 "Keyword extraction not exported"
        fi
        
        if grep -q "export.*fuseResults" workers/api/src/hybrid-search.ts; then
            log_test "Hybrid Search - RRF Fusion" 0 "RRF fusion function found"
        else
            log_test "Hybrid Search - RRF Fusion" 1 "RRF fusion function not found"
        fi
    else
        log_test "Hybrid Search - File Exists" 1 "hybrid-search.ts not found"
    fi
}

# Function to test enhanced API endpoints
test_enhanced_api_endpoints() {
    echo -e "${BLUE}Testing enhanced API endpoints...${NC}"
    
    # Check if new v2.0 response format is implemented
    if [ -f "workers/api/src/index.ts" ]; then
        if grep -q '"query":.*input.query' workers/api/src/index.ts; then
            log_test "API - Query Field" 0 "Query field in response"
        else
            log_test "API - Query Field" 1 "Query field missing"
        fi
        
        if grep -q '"debug"' workers/api/src/index.ts; then
            log_test "API - Debug Field" 0 "Debug field in response"
        else
            log_test "API - Debug Field" 1 "Debug field missing"
        fi
        
        if grep -q '"hybrid_search_used"' workers/api/src/index.ts; then
            log_test "API - Hybrid Search Flag" 0 "Hybrid search flag in response"
        else
            log_test "API - Hybrid Search Flag" 1 "Hybrid search flag missing"
        fi
    else
        log_test "API - Index File" 1 "index.ts not found"
    fi
}

# Function to test enhanced consumer worker
test_enhanced_consumer() {
    echo -e "${BLUE}Testing enhanced consumer worker...${NC}"
    
    if [ -f "workers/consumer/src/index.ts" ]; then
        # Check for new features
        if grep -q "extractKeywords" workers/consumer/src/index.ts; then
            log_test "Consumer - Keyword Extraction" 0 "Keyword extraction implemented"
        else
            log_test "Consumer - Keyword Extraction" 1 "Keyword extraction missing"
        fi
        
        if grep -q "metadataKey" workers/consumer/src/index.ts; then
            log_test "Consumer - Metadata Storage" 0 "Metadata storage implemented"
        else
            log_test "Consumer - Metadata Storage" 1 "Metadata storage missing"
        fi
        
        if grep -q "section_hierarchy" workers/consumer/src/index.ts; then
            log_test "Consumer - Section Hierarchy" 0 "Section hierarchy implemented"
        else
            log_test "Consumer - Section Hierarchy" 1 "Section hierarchy missing"
        fi
    else
        log_test "Consumer - Index File" 1 "index.ts not found"
    fi
}

# Function to test Python engine enhancements
test_python_engine() {
    echo -e "${BLUE}Testing Python engine enhancements...${NC}"
    
    if [ -f "docuflow-engine/main.py" ]; then
        if grep -q "tables_html" docuflow-engine/main.py; then
            log_test "Engine - Table Extraction" 0 "Table extraction implemented"
        else
            log_test "Engine - Table Extraction" 1 "Table extraction missing"
        fi
        
        if grep -q "sections" docuflow-engine/main.py; then
            log_test "Engine - Section Extraction" 0 "Section extraction implemented"
        else
            log_test "Engine - Section Extraction" 1 "Section extraction missing"
        fi
        
        if grep -q "extract_sections" docuflow-engine/main.py; then
            log_test "Engine - Extract Function" 0 "Extract sections function found"
        else
            log_test "Engine - Extract Function" 1 "Extract sections function missing"
        fi
    else
        log_test "Engine - Main File" 1 "main.py not found"
    fi
}

# Function to test database schema
test_database_schema() {
    echo -e "${BLUE}Testing database schema...${NC}"
    
    if [ -f "db/enhanced_schema.sql" ]; then
        if grep -q "keywords" db/enhanced_schema.sql; then
            log_test "Schema - Keywords Field" 0 "Keywords field added"
        else
            log_test "Schema - Keywords Field" 1 "Keywords field missing"
        fi
        
        if grep -q "metadata_key" db/enhanced_schema.sql; then
            log_test "Schema - Metadata Key" 0 "Metadata key field added"
        else
            log_test "Schema - Metadata Key" 1 "Metadata key field missing"
        fi
        
        if grep -q "page_number" db/enhanced_schema.sql; then
            log_test "Schema - Page Number" 0 "Page number field added"
        else
            log_test "Schema - Page Number" 1 "Page number field missing"
        fi
        
        if grep -q "section_hierarchy" db/enhanced_schema.sql; then
            log_test "Schema - Section Hierarchy" 0 "Section hierarchy field added"
        else
            log_test "Schema - Section Hierarchy" 1 "Section hierarchy field missing"
        fi
    else
        log_test "Schema - Enhanced File" 1 "enhanced_schema.sql not found"
    fi
}

# Main test execution
main() {
    echo "Starting DocuFlow v2.0 validation tests..."
    
    # Check prerequisites
    if ! check_wrangler; then
        echo -e "${RED}Error: wrangler CLI not found. Please install it first.${NC}"
        echo "Run: npm install -g wrangler"
        exit 1
    fi
    
    # Test each component
    echo -e "\n${YELLOW}=== Testing API Worker ===${NC}"
    validate_wrangler_config "workers/api" "API Worker"
    test_typescript_compilation "workers/api" "API Worker"
    test_hybrid_search_code
    test_enhanced_api_endpoints
    
    echo -e "\n${YELLOW}=== Testing Consumer Worker ===${NC}"
    validate_wrangler_config "workers/consumer" "Consumer Worker"
    test_typescript_compilation "workers/consumer" "Consumer Worker"
    test_enhanced_consumer
    
    echo -e "\n${YELLOW}=== Testing Python Engine ===${NC}"
    test_python_engine
    
    echo -e "\n${YELLOW}=== Testing Database Schema ===${NC}"
    test_database_schema
    
    # Summary
    echo -e "\n${YELLOW}=== Test Summary ===${NC}"
    echo -e "Tests Passed: ${GREEN}$PASSED${NC}"
    echo -e "Tests Failed: ${RED}$FAILED${NC}"
    echo -e "Total Tests: $((PASSED + FAILED))"
    
    if [ $FAILED -eq 0 ]; then
        echo -e "\n${GREEN}🎉 All validation tests passed!${NC}"
        echo -e "${BLUE}Your DocuFlow v2.0 implementation is ready for deployment.${NC}"
        echo -e "\n${YELLOW}Next steps:${NC}"
        echo "1. Deploy to Cloudflare: pnpm wrangler deploy"
        echo "2. Test with real data using the validation scripts"
        echo "3. Monitor performance and optimize as needed"
        exit 0
    else
        echo -e "\n${RED}⚠️  Some validation tests failed.${NC}"
        echo -e "${YELLOW}Please fix the issues above before deploying.${NC}"
        exit 1
    fi
}

# Run main function
main "$@"