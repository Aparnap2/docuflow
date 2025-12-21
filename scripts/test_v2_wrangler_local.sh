#!/bin/bash
# DocuFlow v2.0 Wrangler Local Testing Script
# Tests new features using wrangler dev environment

set -e

echo "🚀 DocuFlow v2.0 Wrangler Local Testing"
echo "========================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test results
PASSED=0
FAILED=0
WORKERS_PID=()
API_BASE_URL="http://localhost:8787"

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

# Function to check if service is running
check_service() {
    local url=$1
    local timeout=${2:-5}
    
    for i in $(seq 1 $timeout); do
        if curl -s -f "$url/health" > /dev/null 2>&1; then
            return 0
        fi
        sleep 1
    done
    return 1
}

# Function to start wrangler dev
start_wrangler_dev() {
    local worker_dir=$1
    local worker_name=$2
    
    echo -e "${BLUE}Starting $worker_name worker...${NC}"
    cd "$worker_dir"
    
    # Start wrangler dev in background
    pnpm wrangler dev --port $3 > "../logs/${worker_name}.log" 2>&1 &
    local pid=$!
    WORKERS_PID+=($pid)
    
    # Wait for worker to start
    sleep 5
    
    # Check if worker is running
    if kill -0 $pid 2>/dev/null; then
        echo -e "${GREEN}$worker_name worker started (PID: $pid)${NC}"
        return 0
    else
        echo -e "${RED}$worker_name worker failed to start${NC}"
        return 1
    fi
}

# Function to cleanup workers
cleanup_workers() {
    echo -e "\n${YELLOW}Cleaning up workers...${NC}"
    for pid in "${WORKERS_PID[@]}"; do
        if kill -0 $pid 2>/dev/null; then
            kill $pid
            echo "Stopped worker (PID: $pid)"
        fi
    done
}

# Create logs directory
mkdir -p logs

# Set trap to cleanup on exit
trap cleanup_workers EXIT

# Test 1: Start local development environment
echo -e "\n${YELLOW}Test 1: Starting Local Development Environment${NC}"

# Start API worker
if start_wrangler_dev "workers/api" "api" 8787; then
    log_test "API Worker Start" 0 "Running on port 8787"
else
    log_test "API Worker Start" 1 "Failed to start"
    exit 1
fi

# Wait a bit more for API to be fully ready
sleep 3

# Test 2: Health check
echo -e "\n${YELLOW}Test 2: Health Check${NC}"
if check_service "$API_BASE_URL" 10; then
    log_test "API Health Check" 0 "Service is responsive"
else
    log_test "API Health Check" 1 "Service not responding"
fi

# Test 3: Create test project
echo -e "\n${YELLOW}Test 3: Project Creation${NC}"
project_response=$(curl -s -X POST "$API_BASE_URL/v1/projects" \
    -H "Content-Type: application/json" \
    -d '{"name": "V2 Test Project"}' 2>/dev/null || echo "FAILED")

if [[ "$project_response" == *"FAILED"* ]]; then
    log_test "Project Creation" 1 "Request failed"
    PROJECT_ID=""
else
    PROJECT_ID=$(echo "$project_response" | grep -o '"id":"[^"]*"' | cut -d'"' -f4)
    if [ -n "$PROJECT_ID" ]; then
        log_test "Project Creation" 0 "Project ID: $PROJECT_ID"
    else
        log_test "Project Creation" 1 "No project ID returned"
    fi
fi

# Test 4: Create API key
echo -e "\n${YELLOW}Test 4: API Key Creation${NC}"
if [ -n "$PROJECT_ID" ]; then
    api_key_response=$(curl -s -X POST "$API_BASE_URL/v1/api-keys" \
        -H "Content-Type: application/json" \
        -d "{\"project_id\": \"$PROJECT_ID\"}" 2>/dev/null || echo "FAILED")
    
    if [[ "$api_key_response" == *"FAILED"* ]]; then
        log_test "API Key Creation" 1 "Request failed"
        API_KEY=""
    else
        API_KEY=$(echo "$api_key_response" | grep -o '"key":"[^"]*"' | cut -d'"' -f4)
        if [ -n "$API_KEY" ]; then
            log_test "API Key Creation" 0 "API key created successfully"
        else
            log_test "API Key Creation" 1 "No API key returned"
        fi
    fi
else
    log_test "API Key Creation" 1 "No project ID available"
fi

# Test 5: Test hybrid search functionality
echo -e "\n${YELLOW}Test 5: Hybrid Search Functionality${NC}"
if [ -n "$API_KEY" ]; then
    # Test keyword search
    echo "Testing keyword search..."
    keyword_response=$(curl -s -X POST "$API_BASE_URL/v1/query" \
        -H "Authorization: Bearer $API_KEY" \
        -H "Content-Type: application/json" \
        -d '{"query": "test document processing", "mode": "chunks", "top_k": 3}' 2>/dev/null || echo "FAILED")
    
    if [[ "$keyword_response" == *"FAILED"* ]]; then
        log_test "Hybrid Search - Keyword" 1 "Request failed"
    elif [[ "$keyword_response" == *"results"* ]]; then
        result_count=$(echo "$keyword_response" | grep -o '"results":\[' | wc -l)
        log_test "Hybrid Search - Keyword" 0 "Search endpoint working"
    else
        log_test "Hybrid Search - Keyword" 1 "Unexpected response format"
    fi
    
    # Test semantic search
    echo "Testing semantic search..."
    semantic_response=$(curl -s -X POST "$API_BASE_URL/v1/query" \
        -H "Authorization: Bearer $API_KEY" \
        -H "Content-Type: application/json" \
        -d '{"query": "What are the main features?", "mode": "chunks", "top_k": 3}' 2>/dev/null || echo "FAILED")
    
    if [[ "$semantic_response" == *"FAILED"* ]]; then
        log_test "Hybrid Search - Semantic" 1 "Request failed"
    elif [[ "$semantic_response" == *"results"* ]]; then
        log_test "Hybrid Search - Semantic" 0 "Semantic search working"
    else
        log_test "Hybrid Search - Semantic" 1 "Unexpected response format"
    fi
else
    log_test "Hybrid Search" 1 "No API key available"
fi

# Test 6: Test enhanced response format
echo -e "\n${YELLOW}Test 6: Enhanced Response Format${NC}"
if [ -n "$API_KEY" ]; then
    response=$(curl -s -X POST "$API_BASE_URL/v1/query" \
        -H "Authorization: Bearer $API_KEY" \
        -H "Content-Type: application/json" \
        -d '{"query": "test enhanced format", "mode": "chunks", "top_k": 2}' 2>/dev/null || echo "FAILED")
    
    if [[ "$response" == *"FAILED"* ]]; then
        log_test "Enhanced Response Format" 1 "Request failed"
    else
        # Check for new v2.0 fields
        has_debug=$(echo "$response" | grep -q '"debug"' && echo "yes" || echo "no")
        has_query=$(echo "$response" | grep -q '"query"' && echo "yes" || echo "no")
        has_results=$(echo "$response" | grep -q '"results"' && echo "yes" || echo "no")
        
        if [[ "$has_debug" == "yes" ]] && [[ "$has_query" == "yes" ]] && [[ "$has_results" == "yes" ]]; then
            log_test "Enhanced Response Format" 0 "New v2.0 format detected"
        else
            log_test "Enhanced Response Format" 1 "Missing v2.0 fields"
        fi
    fi
else
    log_test "Enhanced Response Format" 1 "No API key available"
fi

# Test 7: Test error handling
echo -e "\n${YELLOW}Test 7: Error Handling${NC}"
# Test with invalid API key
error_response=$(curl -s -X POST "$API_BASE_URL/v1/query" \
    -H "Authorization: Bearer invalid_key" \
    -H "Content-Type: application/json" \
    -d '{"query": "test", "mode": "chunks"}' 2>/dev/null || echo "FAILED")

if [[ "$error_response" == *"FAILED"* ]]; then
    log_test "Error Handling - Invalid Key" 1 "Request failed completely"
elif [[ "$error_response" == *"error"* ]]; then
    log_test "Error Handling - Invalid Key" 0 "Proper error response returned"
else
    log_test "Error Handling - Invalid Key" 1 "No error in response"
fi

# Test 8: Performance metrics
echo -e "\n${YELLOW}Test 8: Performance Metrics${NC}"
if [ -n "$API_KEY" ]; then
    start_time=$(date +%s%3N)
    
    response=$(curl -s -X POST "$API_BASE_URL/v1/query" \
        -H "Authorization: Bearer $API_KEY" \
        -H "Content-Type: application/json" \
        -d '{"query": "performance test", "mode": "chunks", "top_k": 1}' 2>/dev/null || echo "FAILED")
    
    end_time=$(date +%s%3N)
    latency=$((end_time - start_time))
    
    if [[ "$response" == *"FAILED"* ]]; then
        log_test "Performance Test" 1 "Request failed"
    else
        # Check if latency is reasonable (< 5 seconds)
        if [ $latency -lt 5000 ]; then
            log_test "Performance Test" 0 "Response time: ${latency}ms"
        else
            log_test "Performance Test" 1 "Response too slow: ${latency}ms"
        fi
    fi
else
    log_test "Performance Test" 1 "No API key available"
fi

# Test 9: Check logs for any errors
echo -e "\n${YELLOW}Test 9: Log Analysis${NC}"
if [ -f "logs/api.log" ]; then
    error_count=$(grep -c "ERROR\|error\|Error" logs/api.log || echo "0")
    if [ "$error_count" -eq 0 ]; then
        log_test "Log Analysis" 0 "No errors found in logs"
    else
        log_test "Log Analysis" 1 "Found $error_count errors in logs"
        echo "Recent errors:"
        grep "ERROR\|error\|Error" logs/api.log | tail -5
    fi
else
    log_test "Log Analysis" 1 "No log file found"
fi

# Summary
echo -e "\n${YELLOW}Test Summary${NC}"
echo "=============="
echo -e "Tests Passed: ${GREEN}$PASSED${NC}"
echo -e "Tests Failed: ${RED}$FAILED${NC}"
echo -e "Total Tests: $((PASSED + FAILED))"

if [ $FAILED -eq 0 ]; then
    echo -e "\n${GREEN}🎉 All tests passed! DocuFlow v2.0 local development is working correctly.${NC}"
    echo -e "${BLUE}You can now test the full system with real documents and data.${NC}"
    exit 0
else
    echo -e "\n${RED}⚠️  Some tests failed. Please check the issues above.${NC}"
    echo -e "${YELLOW}Check the logs in the 'logs' directory for more details.${NC}"
    exit 1
fi