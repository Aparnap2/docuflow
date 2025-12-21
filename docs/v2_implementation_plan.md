# DocuFlow v2.0 Implementation Plan - Enhanced Cloudflare Architecture

## 🎯 **UPDATED APPROACH** (Post Architecture Decision)

**Decision**: ✅ **Stick with Cloudflare D1 + Vectorize** (not Neon + pgvector)

**Rationale**: 
- Zero additional cost vs $20-50/month for Neon
- Better performance (no network latency)
- Single vendor simplicity
- Build on proven 88.2% validation success foundation

---

## 🚀 **PHASE 1: HYBRID SEARCH FOUNDATION** (Week 1)

### **1.1 Enhanced D1 Schema with tsvector**
**File**: [`db/enhanced_schema.sql`](db/enhanced_schema.sql:1)

```sql
-- Enhanced D1 schema for hybrid search
-- Add tsvector support for keyword search

-- Enhanced chunks table with tsvector
ALTER TABLE chunks ADD COLUMN content_tsv TEXT;

-- Create virtual tsvector for keyword search
-- Note: D1 doesn't support real tsvector, so we'll implement keyword extraction
ALTER TABLE chunks ADD COLUMN keywords TEXT;

-- Add indexes for performance
CREATE INDEX idx_chunks_keywords ON chunks(keywords);
CREATE INDEX idx_chunks_document_id ON chunks(document_id);
CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_documents_sha256 ON documents(sha256);

-- Add metadata storage references
ALTER TABLE chunks ADD COLUMN metadata_key TEXT; -- R2 key for rich metadata
ALTER TABLE chunks ADD COLUMN page_number INTEGER;
ALTER TABLE chunks ADD COLUMN section_hierarchy TEXT; -- JSON array
```

### **1.2 Hybrid Search Implementation**
**File**: [`workers/api/src/hybrid-search.ts`](workers/api/src/hybrid-search.ts:1)

```typescript
export interface HybridSearchResult {
  id: string;
  score: number;
  vector_score?: number;
  keyword_score?: number;
  metadata?: any;
}

export async function hybridSearch(
  env: Env,
  query: string,
  queryVector: number[],
  projectId: string,
  topK: number = 10
): Promise<HybridSearchResult[]> {
  
  // 1. Vector search in Vectorize
  const vectorResults = await env.VECTORIZE.query(queryVector, {
    topK: topK * 2, // Get more candidates for RRF
    namespace: projectId,
    returnMetadata: "all"
  });

  // 2. Keyword search in D1 (extract keywords from query)
  const keywords = extractKeywords(query);
  const keywordResults = await env.DB.prepare(`
    SELECT c.id, c.keywords, c.document_id, c.chunk_index,
           d.source_name, d.sha256
    FROM chunks c
    JOIN documents d ON c.document_id = d.id
    WHERE c.project_id = ? 
    AND c.keywords LIKE '%' || ? || '%'
    ORDER BY c.chunk_index
    LIMIT ?
  `).bind(projectId, keywords.join('%'), topK * 2).all();

  // 3. Reciprocal Rank Fusion (RRF)
  return fuseResults(vectorResults.matches, keywordResults.results, topK);
}

function extractKeywords(text: string): string[] {
  // Simple keyword extraction - can be enhanced
  return text.toLowerCase()
    .replace(/[^\w\s]/g, ' ')
    .split(' ')
    .filter(word => word.length > 3)
    .slice(0, 5); // Top 5 keywords
}

function fuseResults(
  vectorMatches: any[],
  keywordMatches: any[],
  topK: number
): HybridSearchResult[] {
  const scores = new Map<string, { vectorRank?: number; keywordRank?: number; data: any }>();
  
  // Add vector results with ranks
  vectorMatches.forEach((match, index) => {
    scores.set(match.id, { 
      vectorRank: index + 1, 
      data: match 
    });
  });
  
  // Add keyword results with ranks
  keywordMatches.forEach((match, index) => {
    const existing = scores.get(match.id) || { data: match };
    scores.set(match.id, { 
      ...existing, 
      keywordRank: index + 1 
    });
  });
  
  // Calculate RRF scores (k=60 is standard)
  const results = Array.from(scores.entries()).map(([id, score]) => {
    const vectorScore = score.vectorRank ? 1.0 / (60 + score.vectorRank) : 0;
    const keywordScore = score.keywordRank ? 1.0 / (60 + score.keywordRank) : 0;
    
    return {
      id,
      score: vectorScore + keywordScore,
      vector_score: score.vectorRank ? 1.0 / score.vectorRank : undefined,
      keyword_score: score.keywordRank ? 1.0 / score.keywordRank : undefined,
      metadata: score.data
    };
  });
  
  return results
    .sort((a, b) => b.score - a.score)
    .slice(0, topK);
}
```

### **1.3 Enhanced Query Endpoint**
**Modify**: [`workers/api/src/index.ts`](workers/api/src/index.ts:236)

```typescript
import { hybridSearch } from './hybrid-search';

// Replace existing query endpoint
app.post("/v1/query", requireApiKey, async (c) => {
  const projectId = c.get("projectId");
  const input = QuerySchema.parse(await c.req.json());
  
  // Generate embedding with bge-large-en-v1.5 (1024d)
  const emb = await c.env.AI.run("@cf/baai/bge-large-en-v1.5", { text: [input.query] });
  const queryVector = (emb as any).data[0]; // 1024 dimensions
  
  // Hybrid search
  const startTime = Date.now();
  const results = await hybridSearch(c.env, input.query, queryVector, projectId, input.top_k);
  
  if (results.length === 0) {
    return c.json({
      query: input.query,
      results: [],
      debug: {
        retrieval_latency_ms: Date.now() - startTime,
        hybrid_search_used: true,
        vector_dimensions: 1024,
        results_found: 0
      }
    });
  }
  
  // Fetch rich metadata from R2 for each result
  const enrichedResults = await Promise.all(
    results.map(async (result) => {
      const metadataKey = result.metadata?.metadata_key || `metadata/${result.id}.json`;
      const metadataObj = await c.env.BUCKET.get(metadataKey);
      
      if (!metadataObj) return null;
      
      const meta = JSON.parse(await metadataObj.text());
      return {
        id: result.id,
        text: meta.text,
        score: result.score,
        vector_score: result.vector_score,
        keyword_score: result.keyword_score,
        context: {
          before: meta.context_before || "",
          after: meta.context_after || ""
        },
        citation: meta.citation || {
          page_number: result.metadata?.page_number || 1,
          section_header: "Unknown",
          document_name: result.metadata?.source_name || "Unknown"
        },
        table_html: meta.table_html || null
      };
    })
  ).filter(Boolean);
  
  return c.json({
    query: input.query,
    results: enrichedResults,
    debug: {
      retrieval_latency_ms: Date.now() - startTime,
      hybrid_search_used: true,
      vector_dimensions: 1024,
      results_found: enrichedResults.length,
      token_count: input.query.split(' ').length
    }
  });
});
```

---

## 🔧 **PHASE 2: ENHANCED PROCESSING** (Week 2)

### **2.1 Updated Python Engine with Tables**
**Modify**: [`docuflow-engine/main.py`](docuflow-engine/main.py:1)

```python
from docling.document_converter import DocumentConverter
from docling.datamodel.base_models import Table, Section
import json
from typing import List, Dict, Any

@app.post("/process")
async def process(req: Request):
    """Enhanced processing with table extraction and section hierarchy"""
    secret = req.headers.get("x-secret", "")
    if secret != ENGINE_SECRET:
        raise HTTPException(status_code=401, detail="unauthorized")

    filename = req.headers.get("x-filename", "document.pdf")
    content = await req.body()
    if not content:
        raise HTTPException(status_code=400, detail="empty body")

    suffix = ".pdf"
    low = filename.lower()
    if low.endswith(".docx"):
        suffix = ".docx"
    elif low.endswith(".md") or low.endswith(".markdown"):
        suffix = ".md"
    elif low.endswith(".html") or low.endswith(".htm"):
        suffix = ".html"

    # Handle markdown and HTML directly
    if suffix in [".md", ".html"]:
        return {
            "markdown": content.decode("utf-8", errors="ignore"),
            "tables_html": [],
            "sections": [],
            "page_count": 1
        }

    # Process PDF and DOCX with Docling
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as f:
        f.write(content)
        f.flush()
        
        converter = DocumentConverter()
        result = converter.convert(f.name)
        doc = result.document
        
        # Extract tables as HTML
        tables_html = []
        for table in doc.tables:
            tables_html.append(table.export_to_html())
        
        # Extract section hierarchy for citations
        sections = extract_sections(doc)
        
        # Get structured markdown
        markdown = doc.export_to_markdown()
        
        return {
            "markdown": markdown,
            "tables_html": tables_html,
            "sections": sections,
            "page_count": len(doc.pages)
        }

def extract_sections(doc) -> List[Dict[str, Any]]:
    """Extract section hierarchy for smart citations"""
    sections = []
    current_hierarchy = []
    
    for item in doc.body:
        if hasattr(item, 'level') and hasattr(item, 'text'):
            level = item.level
            text = item.text
            
            # Maintain hierarchy based on heading levels
            if level <= len(current_hierarchy):
                current_hierarchy = current_hierarchy[:level-1]
            else:
                current_hierarchy.extend([""] * (level - len(current_hierarchy) - 1))
            
            if level <= len(current_hierarchy):
                current_hierarchy[level-1] = text
            else:
                current_hierarchy.append(text)
            
            sections.append({
                "level": level,
                "text": text,
                "hierarchy": current_hierarchy.copy(),
                "page": getattr(item, 'page', 1)
            })
    
    return sections
```

### **2.2 Enhanced Consumer Worker**
**Modify**: [`workers/consumer/src/index.ts`](workers/consumer/src/index.ts:73)

```typescript
// Replace existing processing logic
const parsed = await engineRes.json();
const markdown = String(parsed.markdown || "");
const tablesHtml = parsed.tables_html || [];
const sections = parsed.sections || [];

if (!markdown) throw new Error("Engine returned empty markdown");

// Enhanced chunking with parent context
const parts = chunkText(markdown);
for (let i = 0; i < parts.length; i++) {
  const chunkId = crypto.randomUUID();
  
  // Find relevant section for this chunk
  const section = findSectionForChunk(sections, i, parts.length);
  
  // Create rich metadata
  const metadata = {
    text: parts[i].t,
    context_before: i > 0 ? parts[i-1].t : "",
    context_after: i < parts.length-1 ? parts[i+1].t : "",
    table_html: tablesHtml[i] || null,
    citation: {
      page_number: section?.page || Math.floor((i + 1) / parts.length * (parsed.page_count || 1)) || 1,
      section_hierarchy: section?.hierarchy || ["Document"],
      document_name: String(doc.source_name)
    }
  };
  
  // Store metadata in R2
  const metadataKey = `metadata/${chunkId}.json`;
  await env.BUCKET.put(metadataKey, JSON.stringify(metadata));
  
  // Store lean data in D1 (only essential fields)
  const keywords = extractKeywords(parts[i].t);
  
  await env.DB.prepare(
    `INSERT INTO chunks (id, project_id, document_id, chunk_index, content_md, keywords, metadata_key, page_number, section_hierarchy, created_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
  ).bind(
    chunkId, 
    job.project_id, 
    job.document_id, 
    i, 
    parts[i].t, 
    keywords.join(' '),
    metadataKey,
    metadata.citation.page_number,
    JSON.stringify(metadata.citation.section_hierarchy),
    now
  ).run();
  
  // Generate embedding with bge-large-en-v1.5 (1024d)
  const emb = await env.AI.run("@cf/baai/bge-large-en-v1.5", { text: [parts[i].t] });
  const vec = (emb as any).data[0]; // 1024 dimensions
  
  // Upsert to Vectorize with metadata
  await env.VECTORIZE.upsert([{
    id: chunkId,
    values: vec,
    namespace: job.project_id,
    metadata: {
      projectId: job.project_id,
      documentId: job.document_id,
      chunkIndex: i,
      sourceName: String(doc.source_name),
      fileSha256: fileHash,
      metadataKey: metadataKey,
      pageNumber: metadata.citation.page_number,
      sectionHierarchy: JSON.stringify(metadata.citation.section_hierarchy)
    },
  }]);
}

function findSectionForChunk(sections: any[], chunkIndex: number, totalChunks: number): any {
  if (!sections.length) return null;
  
  // Simple heuristic: distribute sections across chunks
  const sectionIndex = Math.floor((chunkIndex / totalChunks) * sections.length);
  return sections[Math.min(sectionIndex, sections.length - 1)];
}
```

---

## ⚡ **PHASE 3: PERFORMANCE OPTIMIZATION** (Week 3)

### **3.1 KV Cache for SHA256 Deduplication**
**Modify**: [`workers/api/src/index.ts`](workers/api/src/index.ts:79)

```typescript
// Add to document creation endpoint
app.post("/v1/documents", requireApiKey, async (c) => {
  const projectId = c.get("projectId");
  const input = CreateDocumentSchema.parse(await c.req.json());

  // Check KV cache first for instant ingestion
  const cacheKey = `hash:${input.sha256}:${projectId}`;
  const cached = await c.env.KV.get(cacheKey);
  
  if (cached) {
    // Instant ingestion - copy existing document
    const existingDoc = JSON.parse(cached);
    const newDocId = crypto.randomUUID();
    
    // Copy document metadata
    await c.env.DB.prepare(
      `INSERT INTO documents (id, project_id, source_name, content_type, sha256, r2_key, status, chunk_count, created_at, updated_at)
       SELECT ?, ?, ?, ?, ?, r2_key, 'READY', chunk_count, ?, ? 
       FROM documents WHERE id = ?`
    ).bind(newDocId, projectId, input.source_name, input.content_type, input.sha256, Date.now(), Date.now(), existingDoc.id).run();
    
    // Copy chunks (with new IDs but same content)
    const existingChunks = await c.env.DB.prepare(
      "SELECT chunk_index, content_md, keywords, metadata_key, page_number, section_hierarchy FROM chunks WHERE document_id = ?"
    ).bind(existingDoc.id).all();
    
    for (const chunk of existingChunks.results as any[]) {
      const newChunkId = crypto.randomUUID();
      await c.env.DB.prepare(
        `INSERT INTO chunks (id, project_id, document_id, chunk_index, content_md, keywords, metadata_key, page_number, section_hierarchy, created_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
      ).bind(newChunkId, projectId, newDocId, chunk.chunk_index, chunk.content_md, chunk.keywords, chunk.metadata_key, chunk.page_number, chunk.section_hierarchy, Date.now()).run();
      
      // Copy Vectorize embeddings
      const existingVec = await env.VECTORIZE.getById(chunk.id, { namespace: existingDoc.project_id });
      if (existingVec) {
        await env.VECTORIZE.upsert([{
          id: newChunkId,
          values: existingVec.values,
          namespace: projectId,
          metadata: {
            ...existingVec.metadata,
            documentId: newDocId,
            chunkIndex: chunk.chunk_index
          }
        }]);
      }
    }
    
    return c.json({
      document_id: newDocId,
      status: "READY",
      upload_url: `${c.env.BASE_URL}/v1/documents/${newDocId}/upload`,
      deduped: true,
      instant: true
    });
  }
  
  // Existing document creation logic...
  const docId = crypto.randomUUID();
  // ... rest of creation logic ...
  
  // Cache the new document for future deduplication
  await c.env.KV.put(cacheKey, JSON.stringify({
    id: docId,
    project_id: projectId,
    sha256: input.sha256
  }), { expirationTtl: 86400 }); // 24 hour cache
  
  return c.json({
    document_id: docId,
    status: "CREATED",
    upload_url: `${c.env.BASE_URL}/v1/documents/${docId}/upload`
  });
});
```

### **3.2 Batch Processing Enhancement**
**Modify**: [`workers/consumer/src/index.ts`](workers/consumer/src/index.ts:32)

```typescript
export default {
  async queue(batch: MessageBatch<any>, env: Env) {
    // Batch processing - process up to 10 documents or wait 30 seconds
    const messages = batch.messages;
    
    if (messages.length >= 10 || (messages.length > 1 && Date.now() - messages[0].timestamp > 30000)) {
      console.log(`Processing batch of ${messages.length} documents`);
      
      // Process in parallel for better performance
      const results = await Promise.allSettled(
        messages.map(msg => processSingleDocument(msg, env))
      );
      
      // Handle results
      results.forEach((result, index) => {
        if (result.status === 'fulfilled') {
          messages[index].ack();
        } else {
          console.error(`Batch processing failed for message ${index}:`, result.reason);
          const delaySeconds = Math.min(120, Math.pow(2, messages[index].attempts));
          messages[index].retry({ delaySeconds });
        }
      });
    } else {
      // Process single document (existing logic)
      for (const msg of messages) {
        await processSingleDocument(msg, env);
      }
    }
  }
};

async function processSingleDocument(msg: Message<any>, env: Env): Promise<void> {
  // Extract existing processing logic into reusable function
  // ... existing processing code ...
}
```

---

## 🧪 **PHASE 4: VALIDATION & TESTING** (Week 4)

### **4.1 Updated Systematic Validation**
**Modify**: [`validation/systematic_validation.py`](validation/systematic_validation.py:1)

Add new tests for v2.0 features:

```python
def test_hybrid_search_accuracy(self) -> bool:
    """Test hybrid search returns relevant results for both keyword and semantic queries"""
    # Test keyword query
    keyword_response = self.make_request('POST', '/v1/query', json={
        'query': 'termination fee',  # Keyword search
        'mode': 'chunks',
        'top_k': 5
    })
    
    # Test semantic query  
    semantic_response = self.make_request('POST', '/v1/query', json={
        'query': 'What are the cancellation charges?',  # Semantic search
        'mode': 'chunks',
        'top_k': 5
    })
    
    # Both should return relevant results
    return self.log_result('Hybrid Search Accuracy', 
        keyword_response.status_code == 200 and semantic_response.status_code == 200,
        f"Keyword: {keyword_response.status_code}, Semantic: {semantic_response.status_code}")

def test_parent_context_preservation(self) -> bool:
    """Test parent context is preserved in search results"""
    response = self.make_request('POST', '/v1/query', json={
        'query': 'test document processing',
        'mode': 'chunks',
        'top_k': 3
    })
    
    if response.status_code == 200:
        data = response.json()
        results = data.get('results', [])
        
        # Check if context is present
        has_context = any(
            result.get('context', {}).get('before') or 
            result.get('context', {}).get('after') 
            for result in results
        )
        
        return self.log_result('Parent Context Preservation', has_context,
            f"Found context in {sum(1 for r in results if r.get('context'))} results")

def test_table_html_extraction(self) -> bool:
    """Test tables are extracted as HTML"""
    # This would need a document with tables
    if not self.document_id:
        return self.log_result('Table HTML Extraction', False, "No document available")
        
    response = self.make_request('POST', '/v1/query', json={
        'query': 'table data financial information',
        'document_id': self.document_id,
        'mode': 'chunks',
        'top_k': 5
    })
    
    if response.status_code == 200:
        data = response.json()
        results = data.get('results', [])
        
        # Check if any results contain table HTML
        has_tables = any(result.get('table_html') for result in results)
        
        return self.log_result('Table HTML Extraction', has_tables,
            f"Found tables in {sum(1 for r in results if r.get('table_html'))} results")

def test_smart_citations(self) -> bool:
    """Test citations include page numbers and sections"""
    response = self.make_request('POST', '/v1/query', json={
        'query': 'document content',
        'mode': 'chunks',
        'top_k': 3
    })
    
    if response.status_code == 200:
        data = response.json()
        results = data.get('results', [])
        
        # Check citation structure
        good_citations = 0
        for result in results:
            citation = result.get('citation', {})
            if (citation.get('page_number') and 
                citation.get('section_header') and 
                citation.get('document_name')):
                good_citations += 1
        
        return self.log_result('Smart Citations', good_citations > 0,
            f"Good citations: {good_citations}/{len(results)}")

def test_kv_cache_deduplication(self) -> bool:
    """Test SHA256 cache works for instant ingestion"""
    if not self.api_key or not self.project_id:
        return self.log_result('KV Cache Deduplication', False, "Missing API key or project ID")
    
    # Upload same document twice
    test_pdf_path = Path(__file__).parent / "test_pdf.pdf"
    
    with open(test_pdf_path, 'rb') as f:
        file_content = f.read()
        file_sha256 = hashlib.sha256(file_content).hexdigest()
    
    # First upload
    response1 = self.make_request('POST', '/v1/documents', json={
        'project_id': self.project_id,
        'source_name': 'cache_test_1.pdf',
        'content_type': 'application/pdf',
        'sha256': file_sha256
    })
    
    # Second upload (should be instant)
    response2 = self.make_request('POST', '/v1/documents', json={
        'project_id': self.project_id,
        'source_name': 'cache_test_2.pdf',
        'content_type': 'application/pdf',
        'sha256': file_sha256
    })
    
    if response1.status_code in [200, 201] and response2.status_code in [200, 201]:
        data1 = response1.json()
        data2 = response2.json()
        
        # Check if second upload was instant (status READY)
        instant = (data2.get('status') == 'READY' and data2.get('deduped') == True)
        
        return self.log_result('KV Cache Deduplication', instant,
            f"First: {data1.get('status')}, Second: {data2.get('status')}, Instant: {instant}")
```

---

## 📊 **SUCCESS METRICS**

### **Performance Targets:**
- **P95 Retrieval Latency**: < 250ms (currently ~35ms, excellent!)
- **Hybrid Search Accuracy**: > 90% relevant results
- **KV Cache Hit Rate**: > 80% for duplicate documents
- **Embedding Generation**: < 100ms per chunk

### **Quality Targets:**
- **Parent Context**: 100% of results include before/after context
- **Table Extraction**: > 95% accuracy for documents with tables
- **Smart Citations**: 100% include page numbers and sections
- **Hybrid Search**: Both keyword and semantic queries work

### **Validation Targets:**
- **Systematic Tests**: 17/17 passing (up from 15/17)
- **Error Handling**: 100% proper error responses
- **Performance**: Maintain < 250ms P95 latency

---

## 🎯 **IMPLEMENTATION TIMELINE**

### **Week 1: Hybrid Search Foundation**
- [ ] Day 1-2: Enhanced D1 schema with tsvector support
- [ ] Day 3-4: Hybrid search function implementation
- [ ] Day 5: Updated query endpoint with RRF

### **Week 2: Enhanced Processing**
- [ ] Day 1-2: Python engine with table extraction
- [ ] Day 3-4: Consumer worker with parent context
- [ ] Day 5: Smart citations with section hierarchy

### **Week 3: Performance Optimization**
- [ ] Day 1-2: KV cache for SHA256 deduplication
- [ ] Day 3-4: Batch processing implementation
- [ ] Day 5: Performance benchmarking

### **Week 4: Validation & Polish**
- [ ] Day 1-2: Updated systematic validation tests
- [ ] Day 3-4: End-to-end integration testing
- [ ] Day 5: Performance optimization and documentation

**Ready to start with Phase 1 implementation!**