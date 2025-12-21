#!/bin/bash
BASE_URL="http://localhost:8787"
API_KEY="sk-test-key"

echo "🧪 Testing Local DocuFlow Stack..."

# 1. Create project & API key (mocked in code)
echo "1. Creating test project..."
curl -s -X POST "$BASE_URL/v1/projects" \
  -H "Content-Type: application/json" \
  -d '{"name": "Local Test"}' | jq .

# 2. Upload document (real PDF file needed)
echo "2. Uploading test document..."
curl -s -X POST "$BASE_URL/v1/documents" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"filename": "test.pdf", "sha256": "fakehash123"}' | jq . > doc_response.json

DOC_ID=$(jq -r '.document_id' doc_response.json)
echo "📄 Created doc: $DOC_ID"

# 3. Upload file bytes (create a 1KB dummy PDF first)
echo -n "%PDF-1.4 Dummy PDF for testing" > test.pdf
curl -s -X PUT "$BASE_URL/v1/documents/$DOC_ID/upload" \
  -H "Authorization: Bearer $API_KEY" \
  --data-binary @test.pdf | jq .

# 4. Trigger processing
echo "3. Starting processing..."
curl -s -X POST "$BASE_URL/v1/documents/$DOC_ID/process" \
  -H "Authorization: Bearer $API_KEY" | jq .

echo "⏳ Processing... (check Terminal 3 for queue logs)"
sleep 10

# 5. Check status
echo "4. Checking status..."
curl -s "$BASE_URL/v1/documents/$DOC_ID" \
  -H "Authorization: Bearer $API_KEY" | jq .

# 6. Query it!
echo "5. Querying document..."
curl -s -X POST "$BASE_URL/v1/query" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "test"}' | jq .

echo "✅ Local E2E test complete!"
rm test.pdf doc_response.json
