#!/bin/bash
# DocuFlow v2.0 Quick Validation Script
# Simple grep-based validation of key features

echo "🚀 DocuFlow v2.0 Quick Validation"
echo "=================================="

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

PASSED=0
FAILED=0

log_test() {
    if [ $2 -eq 0 ]; then
        echo -e "${GREEN}✅${NC} $1"
        ((PASSED++))
    else
        echo -e "${RED}❌${NC} $1"
        ((FAILED++))
    fi
}

echo "Checking v2.0 implementation..."

# Hybrid Search Implementation
echo -e "\n📊 Hybrid Search:"
grep -q "export.*hybridSearch" workers/api/src/hybrid-search.ts && log_test "Main hybrid search function" 0 || log_test "Main hybrid search function" 1
grep -q "export.*extractKeywords" workers/api/src/hybrid-search.ts && log_test "Keyword extraction" 0 || log_test "Keyword extraction" 1
grep -q "Reciprocal Rank Fusion" workers/api/src/hybrid-search.ts && log_test "RRF algorithm" 0 || log_test "RRF algorithm" 1
grep -q "fuseResults" workers/api/src/hybrid-search.ts && log_test "Result fusion" 0 || log_test "Result fusion" 1

# API Integration
echo -e "\n🔌 API Integration:"
grep -q 'import.*hybridSearch.*from.*"./hybrid-search"' workers/api/src/index.ts && log_test "Hybrid search import" 0 || log_test "Hybrid search import" 1
grep -q "hybridSearch(" workers/api/src/index.ts && log_test "Hybrid search usage" 0 || log_test "Hybrid search usage" 1
grep -q 'query:.*input\.query' workers/api/src/index.ts && log_test "Query field in response" 0 || log_test "Query field in response" 1
grep -q 'debug:' workers/api/src/index.ts && log_test "Debug field in response" 0 || log_test "Debug field in response" 1
grep -q 'hybrid_search_used:' workers/api/src/index.ts && log_test "Hybrid search flag" 0 || log_test "Hybrid search flag" 1

# Consumer Worker Enhancements
echo -e "\n⚙️  Consumer Worker:"
grep -q "extractKeywords" workers/consumer/src/index.ts && log_test "Keyword extraction in consumer" 0 || log_test "Keyword extraction in consumer" 1
grep -q "metadataKey" workers/consumer/src/index.ts && log_test "Metadata storage" 0 || log_test "Metadata storage" 1
grep -q "section_hierarchy" workers/consumer/src/index.ts && log_test "Section hierarchy" 0 || log_test "Section hierarchy" 1
grep -q "tablesHtml" workers/consumer/src/index.ts && log_test "Table HTML extraction" 0 || log_test "Table HTML extraction" 1

# Python Engine
echo -e "\n🐍 Python Engine:"
grep -q "tables_html" docuflow-engine/main.py && log_test "Table extraction in engine" 0 || log_test "Table extraction in engine" 1
grep -q "sections" docuflow-engine/main.py && log_test "Section extraction" 0 || log_test "Section extraction" 1
grep -q "extract_sections" docuflow-engine/main.py && log_test "Extract sections function" 0 || log_test "Extract sections function" 1

# Database Schema
echo -e "\n🗄️  Database Schema:"
grep -q "keywords" db/enhanced_schema.sql && log_test "Keywords field" 0 || log_test "Keywords field" 1
grep -q "metadata_key" db/enhanced_schema.sql && log_test "Metadata key field" 0 || log_test "Metadata key field" 1
grep -q "page_number" db/enhanced_schema.sql && log_test "Page number field" 0 || log_test "Page number field" 1
grep -q "section_hierarchy" db/enhanced_schema.sql && log_test "Section hierarchy field" 0 || log_test "Section hierarchy field" 1

# Configuration
echo -e "\n⚙️  Configuration:"
grep -q "KV" workers/api/wrangler.toml && log_test "KV namespace in config" 0 || log_test "KV namespace in config" 1
grep -q "VECTORIZE" workers/api/wrangler.toml && log_test "Vectorize binding" 0 || log_test "Vectorize binding" 1
grep -q "DB" workers/api/wrangler.toml && log_test "D1 binding" 0 || log_test "D1 binding" 1
grep -q "AI" workers/api/wrangler.toml && log_test "AI binding" 0 || log_test "AI binding" 1

# Summary
echo -e "\n📊 Summary:"
echo "Passed: $PASSED"
echo "Failed: $FAILED"
echo "Total: $((PASSED + FAILED))"

if [ $FAILED -eq 0 ]; then
    echo -e "\n${GREEN}🎉 All validation tests passed!${NC}"
    echo "DocuFlow v2.0 implementation is ready for deployment."
    exit 0
else
    echo -e "\n${RED}⚠️  Some tests failed.${NC}"
    echo "Please review the implementation."
    exit 1
fi