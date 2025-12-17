// Basic syntax check for core types
import { z } from 'zod';

const QueueJobSchema = z.object({
  docId: z.string(),
  workspaceId: z.string(),
});
export type QueueJob = z.infer<typeof QueueJobSchema>;

const EngineCallbackSchema = z.object({
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
export type EngineCallback = z.infer<typeof EngineCallbackSchema>;

// Simple function to validate the types exist
export function validateTypes(job: QueueJob, callback: EngineCallback) {
  return {
    job: job.docId,
    callback: callback.status
  };
}

console.log("✓ Basic TS syntax validation passed");