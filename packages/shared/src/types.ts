import { z } from "zod";

// Document creation schemas
export const CreateDocumentSchema = z.object({
  source_name: z.string().min(1),
  content_type: z.string().min(1),
  sha256: z.string().min(16),
});

export const BatchCreateSchema = z.object({
  documents: z.array(CreateDocumentSchema).min(1).max(200),
});

// Query schema for RAG operations
export const QuerySchema = z.object({
  query: z.string().min(1),
  document_id: z.string().optional(),
  top_k: z.number().int().min(1).max(20).default(5),
  mode: z.enum(["chunks", "answer"]).default("chunks"),
});

// Ingest job for queue processing
export const IngestJobSchema = z.object({
  project_id: z.string(),
  document_id: z.string(),
});

export type IngestJob = z.infer<typeof IngestJobSchema>;

// Webhook event schema
export const WebhookEventSchema = z.object({
  project_id: z.string(),
  type: z.enum(["document.ready", "document.failed"]),
  data: z.any(),
  webhook_id: z.string(),
  attempt: z.number().int().min(0).max(20),
});

export type WebhookEvent = z.infer<typeof WebhookEventSchema>;

// Document status enum
export const DocumentStatus = {
  CREATED: "CREATED",
  UPLOADED: "UPLOADED", 
  PROCESSING: "PROCESSING",
  READY: "READY",
  FAILED: "FAILED",
  DELETED: "DELETED"
} as const;

export type DocumentStatusType = typeof DocumentStatus[keyof typeof DocumentStatus];

// API response schemas
export const DocumentResponseSchema = z.object({
  document_id: z.string(),
  status: z.string(),
  upload_url: z.string(),
  deduped: z.boolean().optional(),
});

export const QueryResponseSchema = z.object({
  mode: z.enum(["chunks", "answer"]),
  chunks: z.array(z.any()).optional(),
  citations: z.array(z.any()).optional(),
  answer: z.string().optional(),
});

// Legacy schemas (to be removed after full migration)
export const QueueJobSchema = z.object({
  docId: z.string(),
  workspaceId: z.string(),
});

export const EngineCallbackSchema = z.object({
  status: z.enum(["COMPLETED", "FAILED"]),
  data: z.object({
    vendor_name: z.string().nullable(),
    total_amount: z.number().nullable(),
    invoice_date: z.string().nullable(),
    invoice_number: z.string().nullable(),
    currency: z.string().nullable(),
  }).optional(),
  drive_file_id: z.string().nullable(),
  error: z.string().nullable(),
});