import { z } from 'zod';

// User schema
export const UserSchema = z.object({
  id: z.string().uuid(),
  email: z.string().email(),
  name: z.string().nullable(),
  createdAt: z.string().datetime(),
  updatedAt: z.string().datetime(),
  stripeCustomerId: z.string().nullable(),
  stripeSubscriptionId: z.string().nullable(),
  stripePriceId: z.string().nullable(),
  stripeCurrentPeriodEnd: z.string().datetime().nullable(),
});

// Document schema
export const DocumentSchema = z.object({
  id: z.string().uuid(),
  userId: z.string().uuid(), // Foreign key reference to User
  originalName: z.string(),
  originalSize: z.number().int().positive(),
  originalMimeType: z.string(),
  status: z.enum(['processing', 'completed', 'failed']),
  s3Key: z.string(),
  parsedContent: z.string().optional(),
  parsedStructure: z.string().optional(), // JSON string of parsed document structure
  webhookUrl: z.string().url().optional(),
  webhookSecret: z.string().optional(),
  createdAt: z.string().datetime(),
  updatedAt: z.string().datetime(),
  completedAt: z.string().datetime().nullable(),
});

// Document creation schema (for API requests)
export const CreateDocumentSchema = z.object({
  originalName: z.string(),
  originalSize: z.number().int().positive(),
  originalMimeType: z.string(),
  webhookUrl: z.string().url().optional(),
  webhookSecret: z.string().optional(),
});

// Document update schema
export const UpdateDocumentSchema = z.object({
  status: z.enum(['processing', 'completed', 'failed']).optional(),
  parsedContent: z.string().optional(),
  parsedStructure: z.string().optional(),
  completedAt: z.string().datetime().optional(),
});

// Queue message schema for document processing
export const DocumentQueueMessageSchema = z.object({
  documentId: z.string().uuid(),
  userId: z.string().uuid(),
  s3Key: z.string(),
  originalMimeType: z.string(),
});

// Webhook payload schema
export const WebhookPayloadSchema = z.object({
  documentId: z.string().uuid(),
  userId: z.string().uuid(),
  status: z.enum(['processing', 'completed', 'failed']),
  downloadUrl: z.string().url().optional(),
});

// Export inferred types
export type User = z.infer<typeof UserSchema>;
export type Document = z.infer<typeof DocumentSchema>;
export type CreateDocument = z.infer<typeof CreateDocumentSchema>;
export type UpdateDocument = z.infer<typeof UpdateDocumentSchema>;
export type DocumentQueueMessage = z.infer<typeof DocumentQueueMessageSchema>;
export type WebhookPayload = z.infer<typeof WebhookPayloadSchema>;