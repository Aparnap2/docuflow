Of course. I have analyzed your original PRD, our conversations, and the "Squeeze Report" to generate a new, comprehensive Product Requirements Document.

This PRD replaces the previous version. The old one was a good start but relied on Cloudflare Vectorize/D1 and missed key optimizations. This new version is built around the **"$0 Architecture"**, focusing on Supabase for Hybrid Search, aggressive cost-saving on Cloudflare, and maximum data fidelity from Docling.

Here is the full, updated PRD.

------

# **PRD: DocuFlow v2 - The High-Fidelity RAG API**

**Author:** Gemini
 **Version:** 2.0
 **Date:** 2025-12-21
 **Status:** LOCKED

## 1. Vision & Strategy

## **Vision**

To be the **highest-fidelity document retrieval API** for developers, enabling them to build reliable, trustworthy AI applications without becoming RAG experts.

## **Problem**

Developers at startups need to build "Chat with Docs" features. Existing RAG pipelines are complex, expensive, and produce low-quality, untraceable results. Key pains include:

1. **Poor Data Quality:** Tables are garbled, and document structure is lost.
2. **"Black Box" Answers:** Users don't trust responses without verifiable sources.
3. **High/Unpredictable Costs:** Vector DBs and embedding APIs are expensive.
4. **Slow Performance:** Ingestion and retrieval are slow, creating a poor user experience.

## **Solution: The "Fidelity" API**

DocuFlow v2 is an **Ingest & Retrieval Engine** that solves this by focusing on three pillars:

1. **Quality:** Preserve 100% of document structure (tables, headers) using Docling.
2. **Trust:** Provide "Parent Context" and "Smart Citations" with every response.
3. **Performance at Zero Cost:** Leverage an edge-native, serverless architecture that is aggressively optimized for free tiers.

We are not another LangChain wrapper. We are the **specialized data layer** that makes wrappers work reliably.

## 2. Target Audience (ICP)

- **Company:** Seed or Series A SaaS/software startups.
- **Team Size:** 2-5 full-stack engineers.
- **Need:** Urgently need to add a "Chat with your Docs" feature to their product to close deals or meet roadmap goals.
- **Constraint:** Limited time, limited budget, and no in-house AI/RAG expertise. They value velocity and "it just works" solutions over complex toolkits.

## 3. Key Differentiators (The "Squeeze")

| Feature                        | User Value                                                   | Technical Implementation                                     |
| :----------------------------- | :----------------------------------------------------------- | :----------------------------------------------------------- |
| **Hybrid Search**              | Answers both keyword ("#9942") and semantic ("termination fee") queries correctly. | Postgres `pgvector` (Vectors) + `tsvector` (Keyword) combined with an RRF function. |
| **Parent Context**             | LLM receives surrounding sentences, eliminating fragmented, out-of-context answers. | Chunking logic stores `context_before` and `context_after` in metadata. |
| **Table-as-HTML**              | LLM can read and reason about financial data from tables without hallucinating. | Docling extracts tables to HTML; we store this in R2 and provide it on retrieval. |
| **Smart Citations**            | UI can render clickable citations with page numbers and section headers, building user trust. | Docling extracts structural metadata; we format it into a clean `citations` object. |
| **Zero-Cost Embeddings**       | Dramatically lower cost barrier for startups.                | Cloudflare Workers AI (`bge-base-en-v1.5`) for free, on-the-edge embeddings. |
| **Instant Ingestion (Dedupe)** | Re-uploading the same doc feels instant, improving UX.       | SHA-256 hashing on ingest with a Cloudflare KV cache check.  |
| **Bandwidth Bypass**           | Faster, cheaper document viewing for the end-user.           | Public R2 bucket with a CDN and aggressive caching rules.    |
| **Metadata Compaction**        | Can store millions of vectors in the free Cloudflare tier.   | Vectors in Vectorize; heavy metadata (HTML, text) in R2; lean data in D1. |

## 4. Architecture: The "$0 Stack"

```
textgraph TD
    subgraph User
        direction LR
        A[Upload PDF] --> B{API Worker};
        B --> C[Query];
    end
    subgraph Cloudflare
        B -- 1. Hash --> D[KV Cache];
        D -- Hit --> B;
        D -- Miss --> E[R2 Storage: Raw];
        B -- 2. Queue Job --> F[Queue: Batching];
    end
    subgraph Python Engine (Render)
        G[Docling Processor] -- 4. Parse, Chunk --> H[Get Parent Context];
        H --> I[Store HTML in R2];
    end
    subgraph Cloudflare
        F -- 3. Batch of 10 --> G;
    end
    subgraph Cloudflare (D1 + Vectorize)
        K[Vectors: pgvector]
        L[Keywords: tsvector]
    end
    subgraph Cloudflare
        I -- 5. Embed --> J[Workers AI Embeddings];
        J -- 6. Store --> K;
        J -- 6. Store --> L;
    end
    subgraph Retrieval
       C -- 7. Embed Query --> J;
       J -- 8. Hybrid Search --> M{RRF Function in PG};
       K --> M;
       L --> M;
       M -- 9. Get IDs --> B;
       B -- 10. Fetch Metadata --> E;
       B -- 11. Return Rich JSON --> C;
    end
```

## 5. Detailed Workflows & Schemas

## **A. Ingestion Workflow (Async & Deduplicated)**

1. **`POST /documents`**: Client sends `{ "filename": "contract.pdf" }`.
2. **API Worker (CF)**:
   - Generates a `doc_id` and a presigned `upload_url` for R2.
   - Returns `{ "doc_id": "...", "upload_url": "..." }`.
3. **Client**: `PUT`s the raw file bytes to the `upload_url`.
4. **Client**: `POST /documents/:id/process`.
5. **API Worker (CF)**:
   - Reads the file from R2 and calculates its SHA-256 hash.
   - **KV Check**: Looks up the hash in Cloudflare KV.
     - **Cache Hit**: If found, copies the processed data (chunks, vectors) to the new `doc_id`, marks as `READY`, and finishes. **(Instant Ingestion)**
     - **Cache Miss**: Sends a message `{ "doc_id": "...", "r2_key": "..." }` to the Cloudflare Queue.
6. **Queue Consumer (CF)**: Batches up to 10 messages or waits 30 seconds. Sends the batch to the Python Engine.
7. **Python Engine (Render)**:
   - Receives a batch of documents.
   - For each doc:
     - Uses **Docling** to parse the PDF into structured Markdown, extracting tables as HTML and all metadata (page numbers, headers).
     - Chunks the Markdown, generating "Parent Context" for each chunk.
     - Stores heavy metadata (chunk text, table HTML, parent context) as a single JSON file in R2 (`metadata/<chunk_id>.json`).
     - Sends a batch of chunk texts to the **Embedding Worker**.
8. **Embedding Worker (CF)**:
   - Receives chunk texts.
   - Uses **Workers AI** to generate embeddings.
   - Calls a Supabase Edge Function to insert the lean chunk data (embedding, `tsvector`, `doc_id`, `chunk_idx`) into the Postgres `chunks` table.
9. **Python Engine**: After processing, updates the document status to `READY` via a webhook call back to the API Worker.

------

## **B. Data Models & SQL**

## **Cloudflare D1 + Vectorize Enhanced Schema**

```
sql-- Enable pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- Documents Table
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL,
    filename TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING', -- PENDING, PROCESSING, READY, FAILED
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Chunks Table (LEAN)
CREATE TABLE chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    chunk_idx INTEGER NOT NULL,
    embedding VECTOR(1024) NOT NULL, -- From bge-large-en-v1.5
    content_tsv TSVECTOR, -- For keyword search
    UNIQUE(doc_id, chunk_idx)
);

-- Create HNSW index for fast vector search
CREATE INDEX ON chunks USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

-- Create GIN index for fast keyword search
CREATE INDEX ON chunks USING gin (content_tsv);

-- Function to update tsvector automatically
CREATE OR REPLACE FUNCTION update_chunks_tsv()
RETURNS TRIGGER AS $$
BEGIN
    -- NOTE: The actual text is fetched from R2 in the engine
    -- This is a placeholder; the engine will compute and insert the tsvector.
    NEW.content_tsv := to_tsvector('english', '');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tsv_update_trigger
BEFORE INSERT ON chunks
FOR EACH ROW EXECUTE FUNCTION update_chunks_tsv();
```

## **R2 Metadata Object (`metadata/<chunk_id>.json`)**

```
json{
  "text": "The termination fee is $500.",
  "context_before": "If cancelled within 30 days...",
  "context_after": "This fee is waived if the service is...",
  "table_html": null, // or "<table>...</table>" if present
  "citation": {
    "page_number": 42,
    "section_hierarchy": ["3. Service Terms", "3.1 Fees"],
    "document_name": "Contract_v2.pdf"
  }
}
```

------

## **C. API Response Schema (The "Fidelity" Object)**

**`POST /query` Response:**

```
json{
  "query": "What is the termination fee?",
  "results": [
    {
      "id": "chunk_abc123",
      "text": "The termination fee is $500.",
      "score": 0.92, // RRF Score
      "context": {
        "before": "If cancelled within 30 days of signing, the full deposit is forfeit.",
        "after": "This fee is waived if the cancellation is due to a service outage."
      },
      "citation": {
        "page_number": 42,
        "section_header": "3.1 Fees",
        "document_name": "Contract_v2.pdf"
      },
      "table_html": null // Populated if a table was referenced
    }
  ],
  "debug": {
    "retrieval_latency_ms": 120,
    "hybrid_search_used": true,
    "token_count": 450
  }
}
```

## 6. Core Logic Snippets

## **Hybrid Search Function (SQL for Supabase)**

```
sql-- Reciprocal Rank Fusion (RRF) Function
CREATE OR REPLACE FUNCTION hybrid_rrf_search(
    query_embedding VECTOR(1024),
    query_text TEXT,
    k_val INTEGER DEFAULT 100,
    top_n INTEGER DEFAULT 10
)
RETURNS TABLE (id UUID, score REAL)
AS $$
WITH vector_search AS (
    SELECT id, ROW_NUMBER() OVER (ORDER BY embedding <=> query_embedding) as rank
    FROM chunks
    ORDER BY embedding <=> query_embedding
    LIMIT k_val
),
keyword_search AS (
    SELECT id, ROW_NUMBER() OVER (ORDER BY ts_rank_cd(content_tsv, plainto_tsquery('english', query_text)) DESC) as rank
    FROM chunks
    WHERE content_tsv @@ plainto_tsquery('english', query_text)
    LIMIT k_val
)
SELECT
    id,
    SUM(1.0 / (60 + rank)) AS score -- k=60 is a common RRF constant
FROM (
    SELECT * FROM vector_search
    UNION ALL
    SELECT * FROM keyword_search
) as combined_results
GROUP BY id
ORDER BY score DESC
LIMIT top_n;
$$ LANGUAGE sql;
```

## **Python Engine: Docling + R2 Metadata**

```
python# In Python Engine (main.py)
import boto3 # To interact with R2
import json

def process_document(pdf_bytes):
    # 1. Docling Parsing
    converter = DocumentConverter()
    doc_result = converter.convert(pdf_bytes)
    doc = doc_result.document

    # 2. Chunking & Metadata Generation
    chunks_with_metadata = []
    # (Custom logic to chunk and generate parent context)

    # 3. Store Metadata in R2
    s3_client = boto3.client('s3', endpoint_url='YOUR_R2_ENDPOINT')
    for chunk in chunks_with_metadata:
        chunk_id = chunk['id']
        metadata_payload = {
            "text": chunk['text'],
            "context_before": chunk['context_before'],
            "context_after": chunk['context_after'],
            "table_html": chunk.get('table_html'),
            "citation": chunk['citation']
        }
        s3_client.put_object(
            Bucket='your-r2-metadata-bucket',
            Key=f'metadata/{chunk_id}.json',
            Body=json.dumps(metadata_payload)
        )
        # 4. Send lean data (text for embedding, ids) to Embedding Worker
```

## 7. v1 Non-Goals

- **UI / Dashboard:** This is a headless API-first product.
- **Multi-Source Connectors:** We will only support file uploads (PDF, DOCX) initially. No Notion, GDrive, or web crawlers.
- **Agentic Frameworks:** We are not building a LangGraph runner. We provide the data *for* agents.
- **Complex User Management:** A simple API key per project is sufficient. No RBAC.

## 8. Success Metrics

- **Performance:** P95 Retrieval Latency < 250ms.
- **Quality:** >90% of answers in internal evals must have a correct and verifiable citation.
- **Cost:** Cost per 1M documents ingested < $10.
- **Adoption:** 10 active Seed/Series A customers within 3 months of launch.

1. https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/15359477/2e505027-5909-4239-85db-cafa1c5cb15b/prd.md
