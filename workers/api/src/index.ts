import { Hono } from "hono";
import { cors } from "hono/cors";
import {
  CreateDocumentSchema,
  BatchCreateSchema,
  QuerySchema,
  IngestJobSchema,
  WebhookEventSchema
} from "../../../packages/shared/src/types";
import { hybridSearch, logSearchAnalytics } from "./hybrid-search";

type Env = {
  DB: D1Database;
  BUCKET: R2Bucket;
  VECTORIZE: VectorizeIndex;
  INGEST_QUEUE: Queue;
  EVENTS_QUEUE: Queue;
  AI: Ai;
  BASE_URL: string;
  KV?: KVNamespace; // Optional for local development
  OLLAMA_URL?: string; // Optional for local Ollama testing
};

// LOCAL AI MOCK - Switch between Cloudflare AI and Ollama for local testing
async function localAI(env: Env, model: string, input: any): Promise<any> {
  // Use Ollama for local testing if available, otherwise fall back to Cloudflare AI
  if (env.OLLAMA_URL) {
    try {
      console.log(`Using Ollama for local AI: ${model}`);
      
      if (model.includes("bge") || model.includes("embedding")) {
        // Use Ollama for embeddings
        const ollamaUrl = env.OLLAMA_URL || 'http://localhost:11434';
        const response = await fetch(`${ollamaUrl}/api/embeddings`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            model: 'nomic-embed-text:v1.5',
            prompt: Array.isArray(input.text) ? input.text[0] : input.text
          })
        });
        
        if (!response.ok) {
          throw new Error(`Ollama embedding failed: ${response.status}`);
        }
        
        const result = await response.json();
        return {
          data: [result.embedding] // Convert to Cloudflare AI format
        };
      } else if (model.includes("qwen")) {
        // Use Ollama for text generation
        const ollamaUrl = env.OLLAMA_URL || 'http://localhost:11434';
        const response = await fetch(`${ollamaUrl}/api/generate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            model: 'qwen3:3b',
            prompt: input.messages ? input.messages.map((m: any) => `${m.role}: ${m.content}`).join('\n') : input.prompt,
            stream: false
          })
        });
        
        if (!response.ok) {
          throw new Error(`Ollama generation failed: ${response.status}`);
        }
        
        const result = await response.json();
        return {
          response: result.response
        };
      }
    } catch (ollamaError) {
      console.warn(`Ollama failed, falling back to Cloudflare AI:`, ollamaError);
      // Fall through to Cloudflare AI
    }
  }
  
  // Use Cloudflare AI (works in production or remote dev)
  try {
    console.log(`Using Cloudflare AI: ${model}`);
    return await env.AI.run(model, input);
  } catch (cfError) {
    console.error(`Cloudflare AI failed:`, cfError);
    throw cfError;
  }
}

const app = new Hono<{ Bindings: Env; Variables: { projectId: string } }>();
app.use("/*", cors());

// Database initialization
async function initializeDatabase(c: any) {
  try {
    // Check if tables exist
    const testQuery = await c.env.DB.prepare("SELECT name FROM sqlite_master WHERE type='table' AND name='projects'").first();
    if (testQuery) {
      console.log("Database already initialized");
      return;
    }

    console.log("Initializing database schema...");
    
    // Create tables
    await c.env.DB.prepare(`
      CREATE TABLE projects (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        created_at INTEGER NOT NULL
      )
    `).run();

    await c.env.DB.prepare(`
      CREATE TABLE api_keys (
        key TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        created_at INTEGER NOT NULL,
        revoked_at INTEGER,
        FOREIGN KEY (project_id) REFERENCES projects(id)
      )
    `).run();

    await c.env.DB.prepare(`
      CREATE TABLE documents (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        source_name TEXT NOT NULL,
        content_type TEXT NOT NULL,
        sha256 TEXT NOT NULL,
        r2_key TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('CREATED', 'UPLOADED', 'PROCESSING', 'READY', 'FAILED', 'DELETED')),
        chunk_count INTEGER DEFAULT 0,
        error TEXT,
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL,
        FOREIGN KEY (project_id) REFERENCES projects(id)
      )
    `).run();

    await c.env.DB.prepare(`
      CREATE TABLE chunks (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        document_id TEXT NOT NULL,
        chunk_index INTEGER NOT NULL,
        content_md TEXT NOT NULL,
        keywords TEXT,
        metadata_key TEXT,
        page_number INTEGER,
        section_hierarchy TEXT,
        created_at INTEGER NOT NULL,
        FOREIGN KEY (document_id) REFERENCES documents(id),
        FOREIGN KEY (project_id) REFERENCES projects(id)
      )
    `).run();

    await c.env.DB.prepare(`
      CREATE TABLE webhooks (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        url TEXT NOT NULL,
        secret TEXT NOT NULL,
        created_at INTEGER NOT NULL,
        FOREIGN KEY (project_id) REFERENCES projects(id)
      )
    `).run();

    await c.env.DB.prepare(`
      CREATE TABLE search_analytics (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        query TEXT NOT NULL,
        search_type TEXT NOT NULL,
        results_count INTEGER NOT NULL,
        latency_ms INTEGER NOT NULL,
        created_at INTEGER NOT NULL,
        FOREIGN KEY (project_id) REFERENCES projects(id)
      )
    `).run();

    // Create indexes
    await c.env.DB.prepare("CREATE INDEX idx_documents_project_id ON documents(project_id)").run();
    await c.env.DB.prepare("CREATE INDEX idx_documents_sha256 ON documents(sha256)").run();
    await c.env.DB.prepare("CREATE INDEX idx_documents_status ON documents(status)").run();
    await c.env.DB.prepare("CREATE INDEX idx_chunks_document_id ON chunks(document_id)").run();
    await c.env.DB.prepare("CREATE INDEX idx_chunks_project_id ON chunks(project_id)").run();
    await c.env.DB.prepare("CREATE INDEX idx_api_keys_project_id ON api_keys(project_id)").run();
    await c.env.DB.prepare("CREATE INDEX idx_webhooks_project_id ON webhooks(project_id)").run();
    await c.env.DB.prepare("CREATE INDEX idx_search_analytics_project_id ON search_analytics(project_id)").run();
    await c.env.DB.prepare("CREATE INDEX idx_search_analytics_created_at ON search_analytics(created_at)").run();

    console.log("Database initialization complete");
  } catch (error) {
    console.error("Database initialization failed:", error);
    // Don't throw error, let the worker continue
  }
}

// Add initialization middleware
app.use("*", async (c, next) => {
  await initializeDatabase(c);
  return next();
});

async function requireApiKey(c: any, next: any) {
  const raw = c.req.header("Authorization") || "";
  const key = raw.startsWith("Bearer ") ? raw.slice(7) : "";
  if (!key) return c.json({ error: "Missing API key" }, 401);

  const row = await c.env.DB.prepare("SELECT project_id FROM api_keys WHERE key = ? AND revoked_at IS NULL")
    .bind(key)
    .first();

  if (!row) return c.json({ error: "Invalid API key" }, 403);
  c.set("projectId", String(row.project_id));
  return next();
}

// Project management
app.post("/v1/projects", async (c) => {
  const body = await c.req.json();
  const id = crypto.randomUUID();
  const name = body?.name || "Untitled";
  await c.env.DB.prepare("INSERT INTO projects (id, name, created_at) VALUES (?, ?, ?)")
    .bind(id, name, Date.now())
    .run();
  return c.json({ id, name });
});

// API key management
app.post("/v1/api-keys", async (c) => {
  const body = await c.req.json();
  const projectId = body?.project_id;
  if (!projectId) return c.json({ error: "project_id required" }, 400);

  const key = "sk_" + crypto.randomUUID().replaceAll("-", "");
  await c.env.DB.prepare("INSERT INTO api_keys (key, project_id, created_at) VALUES (?, ?, ?)")
    .bind(key, projectId, Date.now())
    .run();
  return c.json({ key });
});

// Webhook registration
app.post("/v1/webhooks", requireApiKey, async (c) => {
  const projectId = c.get("projectId");
  const body = await c.req.json();
  const url = body?.url;
  if (!url) return c.json({ error: "url required" }, 400);

  const id = crypto.randomUUID();
  const secret = crypto.randomUUID().replaceAll("-", "");
  await c.env.DB.prepare("INSERT INTO webhooks (id, project_id, url, secret, created_at) VALUES (?, ?, ?, ?, ?)")
    .bind(id, projectId, url, secret, Date.now())
    .run();

  return c.json({ webhook_id: id, secret });
});

// Single document creation with KV cache for instant ingestion
app.post("/v1/documents", requireApiKey, async (c) => {
  const projectId = c.get("projectId");
  const input = CreateDocumentSchema.parse(await c.req.json());

  // Check KV cache first for instant ingestion (optional for local dev)
  const cacheKey = `hash:${input.sha256}:${projectId}`;
  const cached = c.env.KV ? await c.env.KV.get(cacheKey) : null;
  
  if (cached) {
    try {
      const existingDoc = JSON.parse(cached);
      console.log(`Cache hit for SHA256 ${input.sha256}, instant ingestion available`);
      
      // Create new document with same content (instant ingestion)
      const newDocId = crypto.randomUUID();
      const newR2Key = `${projectId}/${newDocId}/${input.source_name}`;
      
      // Copy document metadata
      await c.env.DB.prepare(
        `INSERT INTO documents (id, project_id, source_name, content_type, sha256, r2_key, status, chunk_count, created_at, updated_at)
         SELECT ?, ?, ?, ?, ?, ?, 'READY', chunk_count, ?, ?
         FROM documents WHERE id = ?`
      ).bind(newDocId, projectId, input.source_name, input.content_type, input.sha256, newR2Key, Date.now(), Date.now(), existingDoc.id).run();
      
      // Copy chunks with new IDs
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
        try {
          const existingVec = await c.env.VECTORIZE.getById(chunk.id, { namespace: existingDoc.project_id });
          if (existingVec) {
            await c.env.VECTORIZE.upsert([{
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
        } catch (vecError) {
          console.warn(`Failed to copy vector for chunk ${chunk.id}:`, vecError);
        }
      }
      
      console.log(`Instant ingestion complete for document ${newDocId}`);
      
      return c.json({
        document_id: newDocId,
        status: "READY",
        upload_url: `${c.env.BASE_URL}/v1/documents/${newDocId}/upload`,
        deduped: true,
        instant: true
      });
    } catch (cacheError) {
      console.warn(`Cache processing failed for ${input.sha256}:`, cacheError);
      // Fall through to normal processing
    }
  }

  // Normal document creation (existing logic)
  const existing = await c.env.DB.prepare(
    "SELECT id, status FROM documents WHERE project_id = ? AND sha256 = ? AND status != 'DELETED'"
  ).bind(projectId, input.sha256).first();

  if (existing) {
    return c.json({
      document_id: String(existing.id),
      status: String(existing.status),
      upload_url: `${c.env.BASE_URL}/v1/documents/${existing.id}/upload`,
      deduped: true,
    });
  }

  const docId = crypto.randomUUID();
  const r2Key = `${projectId}/${docId}/${input.source_name}`;

  await c.env.DB.prepare(
    `INSERT INTO documents
     (id, project_id, source_name, content_type, sha256, r2_key, status, created_at, updated_at)
     VALUES (?, ?, ?, ?, ?, ?, 'CREATED', ?, ?)`
  ).bind(docId, projectId, input.source_name, input.content_type, input.sha256, r2Key, Date.now(), Date.now()).run();

  // Cache the new document for future deduplication (optional for local dev)
  if (c.env.KV) {
    await c.env.KV.put(cacheKey, JSON.stringify({
      id: docId,
      project_id: projectId,
      sha256: input.sha256
    }), { expirationTtl: 86400 }); // 24 hour cache
  }

  return c.json({
    document_id: docId,
    status: "CREATED",
    upload_url: `${c.env.BASE_URL}/v1/documents/${docId}/upload`,
  });
});

// Batch document creation
app.post("/v1/documents/batch", requireApiKey, async (c) => {
  const projectId = c.get("projectId");
  const input = BatchCreateSchema.parse(await c.req.json());

  const out: any[] = [];
  for (const d of input.documents) {
    const existing = await c.env.DB.prepare(
      "SELECT id, status FROM documents WHERE project_id = ? AND sha256 = ? AND status != 'DELETED'"
    ).bind(projectId, d.sha256).first();

    if (existing) {
      out.push({
        document_id: String(existing.id),
        status: String(existing.status),
        upload_url: `${c.env.BASE_URL}/v1/documents/${existing.id}/upload`,
        deduped: true,
      });
      continue;
    }

    const docId = crypto.randomUUID();
    const r2Key = `${projectId}/${docId}/${d.source_name}`;

    await c.env.DB.prepare(
      `INSERT INTO documents
       (id, project_id, source_name, content_type, sha256, r2_key, status, created_at, updated_at)
       VALUES (?, ?, ?, ?, ?, ?, 'CREATED', ?, ?)`
    ).bind(docId, projectId, d.source_name, d.content_type, d.sha256, r2Key, Date.now(), Date.now()).run();

    out.push({
      document_id: docId,
      status: "CREATED",
      upload_url: `${c.env.BASE_URL}/v1/documents/${docId}/upload`,
    });
  }

  return c.json({ documents: out });
});

// Document upload endpoint
app.put("/v1/documents/:id/upload", requireApiKey, async (c) => {
  const projectId = c.get("projectId");
  const docId = c.req.param("id");

  const doc = await c.env.DB.prepare(
    "SELECT r2_key, content_type, status FROM documents WHERE id = ? AND project_id = ? AND status != 'DELETED'"
  ).bind(docId, projectId).first();

  if (!doc) return c.json({ error: "Not found" }, 404);

  const body = await c.req.arrayBuffer();
  if (body.byteLength === 0) return c.json({ error: "Empty body" }, 400);

  await c.env.BUCKET.put(String(doc.r2_key), body, {
    httpMetadata: { contentType: String(doc.content_type) },
  });

  await c.env.DB.prepare("UPDATE documents SET status = 'UPLOADED', updated_at = ? WHERE id = ?")
    .bind(Date.now(), docId).run();

  return c.json({ ok: true, status: "UPLOADED" });
});

// Document completion and processing
app.post("/v1/documents/:id/complete", requireApiKey, async (c) => {
  const projectId = c.get("projectId");
  const docId = c.req.param("id");

  const doc = await c.env.DB.prepare(
    "SELECT status FROM documents WHERE id = ? AND project_id = ? AND status != 'DELETED'"
  ).bind(docId, projectId).first();

  if (!doc) return c.json({ error: "Not found" }, 404);
  if (String(doc.status) !== "UPLOADED") return c.json({ error: "Upload required first" }, 400);

  await c.env.DB.prepare("UPDATE documents SET status = 'PROCESSING', updated_at = ? WHERE id = ?")
    .bind(Date.now(), docId).run();

  const job = IngestJobSchema.parse({ project_id: projectId, document_id: docId });
  await c.env.INGEST_QUEUE.send(job);

  return c.json({ ok: true, status: "PROCESSING" });
});

// Get document status
app.get("/v1/documents/:id", requireApiKey, async (c) => {
  const projectId = c.get("projectId");
  const docId = c.req.param("id");

  const doc = await c.env.DB.prepare(
    "SELECT id, status, chunk_count, error, source_name, content_type, sha256, created_at, updated_at FROM documents WHERE id = ? AND project_id = ?"
  ).bind(docId, projectId).first();

  if (!doc) return c.json({ error: "Not found" }, 404);
  
  // Add upload URL if document is in CREATED or UPLOADED status
  const status = String(doc.status);
  const response: any = { ...doc };
  
  if (status === 'CREATED' || status === 'UPLOADED') {
    response.upload_url = `${c.env.BASE_URL}/v1/documents/${docId}/upload`;
  }
  
  return c.json(response);
});

// Delete document
app.delete("/v1/documents/:id", requireApiKey, async (c) => {
  const projectId = c.get("projectId");
  const docId = c.req.param("id");

  const doc = await c.env.DB.prepare("SELECT r2_key FROM documents WHERE id = ? AND project_id = ? AND status != 'DELETED'")
    .bind(docId, projectId).first();
  if (!doc) return c.json({ error: "Not found" }, 404);

  await c.env.DB.prepare("DELETE FROM chunks WHERE document_id = ? AND project_id = ?").bind(docId, projectId).run();
  await c.env.DB.prepare("UPDATE documents SET status = 'DELETED', updated_at = ? WHERE id = ?").bind(Date.now(), docId).run();
  await c.env.BUCKET.delete(String(doc.r2_key));

  return c.json({ ok: true });
});

// Enhanced query endpoint with hybrid search
app.post("/v1/query", requireApiKey, async (c) => {
  const projectId = c.get("projectId");
  const input = QuerySchema.parse(await c.req.json());
  const startTime = Date.now();

  try {
    // Generate embedding using local AI (Ollama for local testing, Cloudflare AI for production)
    const emb = await localAI(c.env, "@cf/baai/bge-large-en-v1.5", { text: [input.query] });
    const queryVector = (emb as any).data[0]; // 1024 dimensions

    // Perform hybrid search
    const searchResults = await hybridSearch(c.env, input.query, queryVector, projectId, {
      topK: input.top_k,
      namespace: projectId,
      includeMetadata: true
    });

    // Log search analytics
    await logSearchAnalytics(c.env, projectId, input.query, 'hybrid', searchResults.length, Date.now() - startTime);

    if (searchResults.length === 0) {
      return c.json({
        query: input.query,
        results: [],
        debug: {
          retrieval_latency_ms: Date.now() - startTime,
          hybrid_search_used: true,
          vector_dimensions: 1024,
          results_found: 0,
          search_type: 'hybrid'
        }
      });
    }

    // Fetch rich metadata from R2 for each result
    const enrichedResults = await Promise.all(
      searchResults.map(async (result) => {
        try {
          const metadataKey = result.metadata?.metadata_key || `metadata/${result.id}.json`;
          const metadataObj = await c.env.BUCKET.get(metadataKey);
          
          if (!metadataObj) {
            console.warn(`Metadata not found for chunk ${result.id}`);
            return null;
          }
          
          const meta = JSON.parse(await metadataObj.text());
          return {
            id: result.id,
            text: meta.text || result.metadata?.content_md || "",
            score: result.score,
            vector_score: result.vector_score,
            keyword_score: result.keyword_score,
            context: {
              before: meta.context_before || "",
              after: meta.context_after || ""
            },
            citation: meta.citation || {
              page_number: result.metadata?.page_number || 1,
              section_header: result.metadata?.section_hierarchy ? JSON.parse(result.metadata.section_hierarchy)[0] : "Unknown",
              document_name: result.metadata?.source_name || "Unknown"
            },
            table_html: meta.table_html || null,
            metadata: {
              document_id: result.metadata?.document_id,
              chunk_index: result.metadata?.chunk_index,
              source_name: result.metadata?.source_name
            }
          };
        } catch (error) {
          console.error(`Error enriching result ${result.id}:`, error);
          return null;
        }
      })
    );

    // Filter out null results and limit to requested top_k
    const validResults = enrichedResults.filter(Boolean).slice(0, input.top_k);

    // Generate answer if requested
    if (input.mode === "answer") {
      const context = validResults.map((r: any) => r.text).join("\n\n");
      // Limit context to avoid token overflow
      const maxContextLength = 4000;
      const truncatedContext = context.length > maxContextLength
        ? context.substring(0, maxContextLength) + "..."
        : context;
      
      try {
        const resp = await localAI(c.env, "@cf/qwen/qwen-3-3b", {
          messages: [
            { role: "system", content: `Answer using only the provided context. If the answer is not in the context, say "I don't have enough information to answer that question."

Context:
${truncatedContext}` },
            { role: "user", content: input.query },
          ],
        });
        
        return c.json({
          mode: input.mode,
          answer: (resp as any).response,
          results: validResults,
          debug: {
            retrieval_latency_ms: Date.now() - startTime,
            hybrid_search_used: true,
            vector_dimensions: 1024,
            results_found: validResults.length,
            search_type: 'hybrid',
            answer_generated: true
          }
        });
      } catch (error) {
        console.error("Answer generation failed:", error);
        return c.json({
          mode: input.mode,
          answer: "I encountered an error generating the answer. Please try again.",
          results: validResults,
          debug: {
            retrieval_latency_ms: Date.now() - startTime,
            hybrid_search_used: true,
            vector_dimensions: 1024,
            results_found: validResults.length,
            search_type: 'hybrid',
            answer_error: true
          }
        }, 500);
      }
    }

    return c.json({
      query: input.query,
      results: validResults,
      debug: {
        retrieval_latency_ms: Date.now() - startTime,
        hybrid_search_used: true,
        vector_dimensions: 1024,
        results_found: validResults.length,
        search_type: 'hybrid'
      }
    });

  } catch (error) {
    console.error("Query processing failed:", error);
    return c.json({
      query: input.query,
      results: [],
      error: "Search failed. Please try again.",
      debug: {
        retrieval_latency_ms: Date.now() - startTime,
        hybrid_search_used: true,
        vector_dimensions: 1024,
        results_found: 0,
        search_type: 'hybrid',
        error: error.message
      }
    }, 500);
  }
});

export default app;