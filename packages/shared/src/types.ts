import { z } from "zod";

export const QueueJobSchema = z.object({
  docId: z.string(),
  workspaceId: z.string(),
});
export type QueueJob = z.infer<typeof QueueJobSchema>;

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
export type EngineCallback = z.infer<typeof EngineCallbackSchema>;