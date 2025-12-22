import { z } from "zod";

// User schemas
export const UserSchema = z.object({
  id: z.string(),
  email: z.string().email(),
  name: z.string().optional(),
  plan: z.enum(['starter', 'pro', 'agency']).default('starter'),
  structurize_email: z.string().optional(),
  created_at: z.number(),
  updated_at: z.number(),
});

export type User = z.infer<typeof UserSchema>;

// Extractor schema (per PRD)
export const ExtractorSchema = z.object({
  id: z.string(),
  user_id: z.string(),
  name: z.string(), // e.g. "Invoices", "Resumes"
  trigger_subject: z.string().optional(), // e.g. "Invoice", "Application" (to route emails)
  target_sheet_id: z.string().optional(), // specific sheet for this extractor type
  schema_json: z.string(), // JSON schema definition
  created_at: z.number(),
  updated_at: z.number(),
});

export type Extractor = z.infer<typeof ExtractorSchema>;

// Schema field definition
export const SchemaFieldSchema = z.object({
  key: z.string(),
  type: z.enum(['string', 'number', 'array', 'boolean', 'date']),
  description: z.string(),
});

export type SchemaField = z.infer<typeof SchemaFieldSchema>;

// Job schema for email processing
export const JobSchema = z.object({
  id: z.string(),
  user_id: z.string(),
  r2_key: z.string(),
  original_name: z.string(),
  sender: z.string(),
  extractor_id: z.string().optional(),
  status: z.enum(['pending', 'processing', 'completed', 'failed']),
  extracted_data: z.string().optional(), // JSON string
  error_message: z.string().optional(),
  created_at: z.number(),
  updated_at: z.number(),
  completed_at: z.number().optional(),
});

export type Job = z.infer<typeof JobSchema>;

// Email ingest job for queue
export const EmailIngestJobSchema = z.object({
  jobId: z.string(),
  userId: z.string(),
  extractorId: z.string().optional(),
});

export type EmailIngestJob = z.infer<typeof EmailIngestJobSchema>;

// Webhook event schema (updated for Structurize)
export const WebhookEventSchema = z.object({
  user_id: z.string(),
  type: z.enum(["job.completed", "job.failed"]),
  data: z.any(),
  attempt: z.number().int().min(0).max(20),
});

export type WebhookEvent = z.infer<typeof WebhookEventSchema>;

// Engine processing request
export const EngineProcessRequestSchema = z.object({
  jobId: z.string(),
  userId: z.string(),
  extractorId: z.string().optional(),
  fileUrl: z.string(), // URL to download the file
  schemaJson: z.string(), // JSON schema for extraction
  callbackUrl: z.string(), // URL to send results
});

export type EngineProcessRequest = z.infer<typeof EngineProcessRequestSchema>;

// Engine response schema
export const EngineResponseSchema = z.object({
  jobId: z.string(),
  status: z.enum(["COMPLETED", "FAILED"]),
  extractedData: z.any().optional(), // Extracted data matching the schema
  error: z.string().optional(),
});

export type EngineResponse = z.infer<typeof EngineResponseSchema>;

// Google Sheets sync request
export const GoogleSheetsSyncRequestSchema = z.object({
  userId: z.string(),
  extractorId: z.string(),
  extractedData: z.any(), // Data matching the extractor schema
});

export type GoogleSheetsSyncRequest = z.infer<typeof GoogleSheetsSyncRequestSchema>;

// Google Sheets auth request
export const GoogleAuthRequestSchema = z.object({
  code: z.string(),
  redirect_uri: z.string(),
});

export type GoogleAuthRequest = z.infer<typeof GoogleAuthRequestSchema>;

// Subscription schema for billing
export const SubscriptionSchema = z.object({
  id: z.string(),
  user_id: z.string(),
  lemonsqueezy_id: z.string(),
  plan: z.enum(['starter', 'pro', 'agency']),
  status: z.enum(['active', 'cancelled', 'expired']),
  renews_at: z.number().optional(),
  ends_at: z.number().optional(),
  created_at: z.number(),
  updated_at: z.number(),
});

export type Subscription = z.infer<typeof SubscriptionSchema>;

// Email processing request from email worker
export const EmailIngestRequestSchema = z.object({
  r2Key: z.string(),
  originalName: z.string(),
  sender: z.string(),
  userId: z.string(),
});

export type EmailIngestRequest = z.infer<typeof EmailIngestRequestSchema>;

// Queue job for email processing
export const QueueJobSchema = z.object({
  jobId: z.string(),
  userId: z.string(),
  extractorId: z.string().optional(),
});

export type QueueJob = z.infer<typeof QueueJobSchema>;