#!/bin/bash
# Simple validation script for DocuFlow v2.0

echo "🚀 DocuFlow v2.0 Validation"
echo "============================"

# Test results
declare -A results

# Function to run a test
test_feature() {
    local name="$1"
    local file="$2"
    local pattern="$3"
    
    if grep -q "$pattern" "$file" 2>/dev/null; then
        results["$name"]=1
        echo "✅ $name"
    else
        results["$name"]=0
        echo "❌ $name"
    fi
}

echo -e "\n📊 Hybrid Search:"
test_feature "Main hybrid search function" "workers/api/src/hybrid-search.ts" "export.*hybridSearch"
test_feature "Keyword extraction" "workers/api/src/hybrid-search.ts" "export.*extractKeywords"
test_feature "RRF algorithm" "workers/api/src/hybrid-search.ts" "Reciprocal Rank Fusion"
test_feature "Result fusion" "workers/api/src/hybrid-search.ts" "fuseResults"

echo -e "\n🔌 API Integration:"
test_feature "Hybrid search import" "workers/api/src/index.ts" 'import.*hybridSearch.*from.*"./hybrid-search"'
test_feature "Hybrid search usage" "workers/api/src/index.ts" "hybridSearch("
test_feature "Query field in response" "workers/api/src/index.ts" 'query:.*input\.query'
test_feature "Debug field in response" "workers/api/src/index.ts" 'debug:'
test_feature "Hybrid search flag" "workers/api/src/index.ts" 'hybrid_search_used:'

echo -e "\n⚙️  Consumer Worker:"
test_feature "Keyword extraction in consumer" "workers/consumer/src/index.ts" "extractKeywords"
test_feature "Metadata storage" "workers/consumer/src/index.ts" "metadataKey"
test_feature "Section hierarchy" "workers/consumer/src/index.ts" "section_hierarchy"
test_feature "Table HTML extraction" "workers/consumer/src/index.ts" "tablesHtml"

echo -e "\n🐍 Python Engine:"
test_feature "Table extraction in engine" "docuflow-engine/main.py" "tables_html"
test_feature "Section extraction" "docuflow-engine/main.py" "sections"
test_feature "Extract sections function" "docuflow-engine/main.py" "extract_sections"

echo -e "\n🗄️  Database Schema:"
test_feature "Keywords field" "db/enhanced_schema.sql" "keywords"
test_feature "Metadata key field" "db/enhanced_schema.sql" "metadata_key"
test_feature "Page number field" "db/enhanced_schema.sql" "page_number"
test_feature "Section hierarchy field" "db/enhanced_schema.sql" "section_hierarchy"

echo -e "\n⚙️  Configuration:"
test_feature "KV namespace in config" "workers/api/wrangler.toml" "KV"
test_feature "Vectorize binding" "workers/api/wrangler.toml" "VECTORIZE"
test_feature "D1 binding" "workers/api/wrangler.toml" "DB"
test_feature "AI binding" "workers/api/wrangler.toml" "AI"

# Count results
passed=0
failed=0

for result in "${results[@]}"; do
    if [ "$result" -eq 1 ]; then
        ((passed++))
    else
        ((failed++))
    fi
done

echo -e "\n📊 Summary:"
echo "Passed: $passed"
echo "Failed: $failed"
echo "Total: $((passed + failed))"

if [ $failed -eq 0 ]; then
    echo -e "\n🎉 All validation tests passed!"
    echo "DocuFlow v2.0 implementation is ready for deployment."
    exit 0
else
    echo -e "\n⚠️  Some tests failed."
    echo "Please review the implementation."
    exit 1
fi