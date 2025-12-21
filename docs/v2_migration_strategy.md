# DocuFlow v2.0 Migration Strategy - Neon Postgres + pgvector

## 🎯 **UPDATED APPROACH** (Based on User Feedback)

### **Key Changes from Original Plan:**
1. **Database**: Neon Serverless Postgres (not Supabase-specific)
2. **Migration Strategy**: Leverage existing code, incremental updates
3. **Architecture**: Evolution, not revolution - keep v1.0 foundations
4. **Timeline**: Flexible, thorough implementation approach

---

## 🔧 **PHASE 1: DATABASE FOUNDATION** 

### **1.1 Neon Postgres Schema with pgvector**
**New File**: [`db/neon_schema.sql`](db/neon_schema.sql:1)

```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Documents Table (LEAN - only essential metadata)
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL,  -- Changed from project_id to workspace_id
    filename TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING', -- PENDING, PROCESSING, READY, FAILED
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(workspace_id, sha256)
);

-- Chunks Table (SUPER LEAN - only vectors and keywords)
CREATE TABLE chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    chunk_idx INTEGER NOT NULL,
    embedding VECTOR(1024) NOT NULL,  -- bge-large-en-v1.5 (from PRD)
    content_tsv TSVECTOR,  -- For keyword search
    UNIQUE(doc_id, chunk_idx)
);

-- Indexes for performance
CREATE INDEX ON chunks USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
CREATE INDEX ON chunks USING gin (content_tsv);
CREATE INDEX idx_chunks_doc_id ON chunks(doc_id);
CREATE INDEX idx_documents_workspace_id ON documents(workspace_id);
CREATE INDEX idx_documents_sha256 ON documents(sha256);

-- RRF Hybrid Search Function
CREATE OR REPLACE FUNCTION hybrid_rrf_search(
    query_embedding VECTOR(1024),
    query_text TEXT,
    workspace_id UUID,
    k_val INTEGER DEFAULT 100,
    top_n INTEGER DEFAULT 10
) RETURNS TABLE (id UUID, score REAL) AS $$
WITH vector_search AS (
    SELECT c.id, ROW_NUMBER() OVER (ORDER BY c.embedding <=> query_embedding) as rank
    FROM chunks c
    JOIN documents d ON c.doc_id = d.id
    WHERE d.workspace_id = hybrid_rrf_search.workspace_id
    ORDER BY c.embedding <=> query_embedding
    LIMIT k_val
),
keyword_search AS (
    SELECT c.id, ROW_NUMBER() OVER (ORDER BY ts_rank_cd(c.content_tsv, plainto_tsquery('english', query_text)) DESC) as rank
    FROM chunks c
    JOIN documents d ON c.doc_id = d.id
    WHERE d.workspace_id = hybrid_rrf_search.workspace_id
    AND c.content_tsv @@ plainto_tsquery('english', query_text)
    ORDER BY rank
    LIMIT k_val
)
SELECT vs.id, SUM(1.0 / (60 + COALESCE(vs.rank, 999))) as score
FROM vector_search vs
FULL OUTER JOIN keyword_search ks ON vs.id = ks.id
GROUP BY vs.id
ORDER BY score DESC
LIMIT top_n;
$$ LANGUAGE sql;
```

### **1.2 Database Connection Layer**
**New File**: [`packages/database/src/neon-client.ts`](packages/database/src/neon-client.ts:1)

```typescript
import { neon } from '@neondatabase/serverless';
import { Pool } from 'pg';

export class NeonClient {
  private pool: Pool;
  
  constructor(connectionString: string) {
    this.pool = new Pool({
      connectionString,
      ssl: { rejectUnauthorized: false }
    });
  }
  
  async query(text: string, params?: any[]): Promise<any> {
    const client = await this.pool.connect();
    try {
      const result = await client.query(text, params);
      return result;
    } finally {
      client.release();
    }
  }
  
  // Hybrid search wrapper
  async hybridSearch(
    queryEmbedding: number[],
    queryText: string,
    workspaceId: string,
    topK: number = 10
  ): Promise<any[]> {
    const result = await this.query(
      'SELECT * FROM hybrid_rrf_search($1, $2, $3, $4, $5)',
      [JSON.stringify(queryEmbedding), queryText, workspaceId, 100, topK]
    );
    return result.rows;
  }
}
```

---

## 🏗️ **PHASE 2: LEVERAGE EXISTING CODE**

### **2.1 Incremental API Worker Updates**
**Modify**: [`workers/api/src/index.ts`](workers/api/src/index.ts:1) - Keep structure, replace DB calls

**Key Changes:**
```typescript
// Replace D1 bindings with Neon client
type Env = {
  NEON_URL: string;  // Instead of DB: D1Database
  BUCKET: R2Bucket;
  // Remove VECTORIZE - using Postgres now
  INGEST_QUEUE: Queue;
  EVENTS_QUEUE: Queue;
  AI: Ai;
  BASE_URL: string;
  KV: KVNamespace;  // For SHA256 cache
};

// Keep existing endpoints, just update DB calls
app.post("/v1/documents", requireApiKey, async (c) => {
  // Same logic, but use Neon client instead of D1
  const neon = new NeonClient(c.env.NEON_URL);
  
  // Check SHA256 in KV cache first
  const cached = await c.env.KV.get(`hash:${input.sha256}`);
  if (cached) {
    // Instant ingestion - copy existing document
    return handleInstantIngestion(cached, input, c.env);
  }
  
  // Existing document creation logic with Neon
  const result = await neon.query(
    'INSERT INTO documents (id, workspace_id, filename, sha256, status) VALUES ($1, $2, $3, $4, $5)',
    [docId, workspaceId, input.source_name, input.sha256, 'PENDING']
  );
});
```

### **2.2 Enhanced Query Endpoint**
**Modify**: [`workers/api/src/index.ts`](workers/api/src/index.ts:236) - Replace Vectorize with hybrid search

```typescript
app.post("/v1/query", requireApiKey, async (c) => {
  const workspaceId = c.get("workspaceId");
  const input = QuerySchema.parse(await c.req.json());
  
  // Generate embedding with bge-large-en-v1.5 (1024d)
  const emb = await c.env.AI.run("@cf/baai/bge-large-en-v1.5", { text: [input.query] });
  const queryVector = (emb as any).data[0]; // 1024 dimensions
  
  // Hybrid search via Neon
  const neon = new NeonClient(c.env.NEON_URL);
  const results = await neon.hybridSearch(queryVector, input.query, workspaceId, input.top_k);
  
  // Fetch rich metadata from R2 for each chunk
  const enrichedResults = await Promise.all(
    results.map(async (result) => {
      const metadata = await c.env.BUCKET.get(`metadata/${result.id}.json`);
      if (!metadata) return null;
      
      const meta = JSON.parse(await metadata.text());
      return {
        id: result.id,
        text: meta.text,
        score: result.score,
        context: {
          before: meta.context_before,
          after: meta.context_after
        },
        citation: meta.citation,
        table_html: meta.table_html
      };
    })
  ).filter(Boolean);
  
  return c.json({
    query: input.query,
    results: enrichedResults,
    debug: {
      retrieval_latency_ms: Date.now() - startTime,
      hybrid_search_used: true,
      token_count: input.query.split(' ').length
    }
  });
});
```

---

## 🔧 **PHASE 3: ENHANCED PROCESSING**

### **3.1 Updated Python Engine**
**Modify**: [`docuflow-engine/main.py`](docuflow-engine/main.py:1) - Add table extraction and context

```python
from docling.document_converter import DocumentConverter
from docling.datamodel.base_models import Table
import json

@app.post("/process")
async def process(req: Request):
    # ... existing auth logic ...
    
    converter = DocumentConverter()
    result = converter.convert(f.name)
    doc = result.document
    
    # Extract tables as HTML
    tables_html = []
    for table in doc.tables:
        tables_html.append(table.export_to_html())
    
    # Get structured content with sections
    markdown = doc.export_to_markdown()
    sections = extract_sections(doc)  # Custom function
    
    # Return enhanced metadata
    return {
        "markdown": markdown,
        "tables_html": tables_html,
        "sections": sections,
        "page_count": len(doc.pages)
    }

def extract_sections(doc):
    """Extract section hierarchy for citations"""
    sections = []
    for item in doc.body:
        if hasattr(item, 'level') and hasattr(item, 'text'):
            sections.append({
                "level": item.level,
                "text": item.text,
                "page": getattr(item, 'page', 1)
            })
    return sections
```

### **3.2 Enhanced Consumer Worker**
**Modify**: [`workers/consumer/src/index.ts`](workers/consumer/src/index.ts:73) - Add parent context and metadata storage

```typescript
// Process with parent context
const parts = chunkText(markdown);
for (let i = 0; i < parts.length; i++) {
  const chunkId = crypto.randomUUID();
  
  // Create rich metadata
  const metadata = {
    text: parts[i].t,
    context_before: i > 0 ? parts[i-1].t : "",
    context_after: i < parts.length-1 ? parts[i+1].t : "",
    table_html: parsed.tables_html[i] || null,
    citation: {
      page_number: i + 1,  // Simplified - would use actual page data
      section_hierarchy: extract_section_hierarchy(parsed.sections, i),
      document_name: String(doc.source_name)
    }
  };
  
  // Store metadata in R2
  await env.BUCKET.put(`metadata/${chunkId}.json`, JSON.stringify(metadata));
  
  // Store lean data in Postgres (only embedding + keywords)
  const embedding = await env.AI.run("@cf/baai/bge-large-en-v1.5", { text: [parts[i].t] });
  const tsvector = parts[i].t.replace(/[^\w\s]/g, ' ').toLowerCase();
  
  await neon.query(
    'INSERT INTO chunks (id, doc_id, chunk_idx, embedding, content_tsv) VALUES ($1, $2, $3, $4, to_tsvector($5))',
    [chunkId, job.document_id, i, JSON.stringify(embedding.data[0]), tsvector]
  );
}
```

---

## 🧪 **PHASE 4: VALIDATION & TESTING**

### **4.1 Updated Systematic Validation**
**Modify**: [`validation/systematic_validation.py`](validation/systematic_validation.py:1) - Add v2.0 specific tests

```python
# New tests for v2.0 features
def test_hybrid_search_accuracy(self) -> bool:
    """Test hybrid search returns relevant results"""
    # Test both keyword and semantic queries
    
def test_parent_context_preservation(self) -> bool:
    """Test parent context is preserved in results"""
    
def test_table_html_extraction(self) -> bool:
    """Test tables are extracted as HTML"""
    
def test_smart_citations(self) -> bool:
    """Test citations include page numbers and sections"""
    
def test_kv_cache_deduplication(self) -> bool:
    """Test SHA256 cache works for instant ingestion"""
```

### **4.2 Performance Benchmarks**
```bash
# Target metrics
P95 Retrieval Latency: < 250ms
Hybrid Search Accuracy: > 90%
KV Cache Hit Rate: > 80%
Embedding Generation: < 100ms per chunk
```

---

## 📋 **IMPLEMENTATION CHECKLIST**

### **Week 1: Database Foundation**
- [ ] Create Neon schema with pgvector
- [ ] Implement Neon client wrapper
- [ ] Update API worker DB calls
- [ ] Test basic CRUD operations

### **Week 2: Hybrid Search**
- [ ] Implement RRF function
- [ ] Update query endpoint
- [ ] Test hybrid search accuracy
- [ ] Performance benchmarking

### **Week 3: Enhanced Processing**
- [ ] Update Python engine with tables
- [ ] Add parent context generation
- [ ] Implement smart citations
- [ ] Update consumer worker

### **Week 4: Polish & Validation**
- [ ] Add KV cache for deduplication
- [ ] Update systematic validation
- [ ] End-to-end testing
- [ ] Performance optimization

---

## 🎯 **SUCCESS CRITERIA**

- ✅ **100% PRD v2.0 Compliance** with Neon Postgres
- ✅ **Hybrid Search** working (keyword + semantic)
- ✅ **Parent Context** preserved in results
- ✅ **Table HTML** extraction from Docling
- ✅ **Smart Citations** with page/section data
- ✅ **Performance**: < 250ms P95 latency
- ✅ **Validation**: 15+/17 tests passing
- ✅ **Zero Breaking Changes** to existing API

**Ready to proceed with Phase 1 implementation!**