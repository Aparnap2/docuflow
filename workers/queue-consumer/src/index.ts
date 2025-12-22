/**
 * Queue Consumer Worker for Structurize
 * Processes email jobs from the queue and sends them to the Python engine for data extraction
 */

import { QueueJob, Extractor } from '@docuflow/shared';

interface Env {
  // Queue for processing email jobs
  INGEST_QUEUE: Queue<any>;

  // Dead letter queue for failed messages
  DLQ_QUEUE: Queue<any>;

  // Python engine URL
  PYTHON_ENGINE_URL: string;

  // Webhook secret for authenticating with the Python engine
  PYTHON_ENGINE_SECRET: string;

  // D1 Database
  DB: D1Database;

  // Web URL for callbacks
  WEB_URL: string;

  // Internal secrets
  WEBHOOK_SECRET: string;
}

export default {
  async queue(batch: MessageBatch<QueueJob>, env: Env): Promise<void> {
    console.log(`Processing batch of ${batch.messages.length} email jobs`);

    // Process all messages in the batch
    const promises = batch.messages.map(async (message) => {
      try {
        // Update job status to processing
        await env.DB.prepare(
          `UPDATE jobs SET status = 'processing', updated_at = ? WHERE id = ?`
        ).bind(Date.now(), message.body.jobId).run();

        const { jobId, userId, extractorId } = message.body;

        console.log(`Processing job ${jobId} for user ${userId} with extractor ${extractorId || 'auto'}`);

        // Get the job details from database
        const jobRow = await env.DB.prepare(
          `SELECT r2_key, original_name, extractor_id FROM jobs WHERE id = ?`
        ).bind(jobId).first();

        if (!jobRow) {
          throw new Error(`Job ${jobId} not found in database`);
        }

        const job = jobRow as any;

        // Get extractor details if extractorId is provided
        let schemaJson = null;
        if (job.extractor_id) {
          const extractorRow = await env.DB.prepare(
            `SELECT schema_json FROM extractors WHERE id = ?`
          ).bind(job.extractor_id).first();

          if (!extractorRow) {
            throw new Error(`Extractor ${job.extractor_id} not found for job ${jobId}`);
          }

          schemaJson = (extractorRow as any).schema_json;
        }

        // Generate a presigned URL for the file in R2
        // In a real implementation, you'd use R2's presigned URL feature
        // For now, we'll assume a proxy endpoint exists
        const fileProxyUrl = `${env.WEB_URL}/api/file-proxy/${job.r2_key}`;

        // Prepare callback URL for when the engine completes processing
        const callbackUrl = `${env.WEB_URL}/api/engine-callback`;

        // Prepare request to Python engine
        const requestBody = {
          jobId: jobId,
          userId: userId,
          extractorId: job.extractor_id || null,
          fileUrl: fileProxyUrl,
          schemaJson: schemaJson, // Will be null for auto-detection
          callbackUrl: callbackUrl
        };

        console.log(`Sending job ${jobId} to Python engine at ${env.PYTHON_ENGINE_URL}`);

        // Send request to Python engine
        const response = await fetch(env.PYTHON_ENGINE_URL, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${env.PYTHON_ENGINE_SECRET}`,
          },
          body: JSON.stringify(requestBody)
        });

        if (!response.ok) {
          const errorText = await response.text();
          console.error(`Python engine error for job ${jobId}: ${response.status} ${response.statusText} - ${errorText}`);
          throw new Error(`Python engine returned ${response.status}: ${errorText}`);
        }

        console.log(`Successfully sent job ${jobId} to Python engine`);

      } catch (error) {
        console.error(`Error processing job ${message.body.jobId}:`, error);

        // Update job status to failed with error message
        try {
          await env.DB.prepare(
            `UPDATE jobs SET status = 'failed', error_message = ?, updated_at = ? WHERE id = ?`
          ).bind(
            error instanceof Error ? error.message : String(error),
            Date.now(),
            message.body.jobId
          ).run();
        } catch (dbError) {
          console.error(`Failed to update job status to failed:`, dbError);
        }

        // Exponential Backoff: 2^attempts seconds with max 600s (10 minutes)
        const delay = Math.min(600, Math.pow(2, message.attempts));
        console.log(`Retrying job ${message.body.jobId} in ${delay}s (attempt ${message.attempts + 1})`);
        message.retry({ delaySeconds: delay });
      }
    });

    // Wait for all messages to be processed
    await Promise.all(promises);
  }
} satisfies ExportedHandler<Env> & QueueConsumer<QueueJob>;