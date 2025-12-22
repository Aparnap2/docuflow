/**
 * Email Ingest Worker for Structurize
 * Processes incoming emails, extracts attachments, stores them in R2, creates job in DB, and queues processing
 */

import { EmailIngestRequestSchema, JobSchema, ExtractorSchema } from '@docuflow/shared';

// Define the environment bindings for Cloudflare Workers
interface Env {
  // R2 Bucket for storing documents
  DOCUMENTS_BUCKET: R2Bucket;

  // Queue for processing documents
  INGEST_QUEUE: Queue<any>;

  // D1 Database
  DB: D1Database;

  // Base URL for internal callbacks
  BASE_URL: string;
}

export default {
  async email(message: ForwardedEmail, env: Env, ctx: ExecutionContext): Promise<void> {
    console.log(`Processing email from ${message.from} to ${message.to}`);

    // Validate size (25MB limit for Cloudflare Workers)
    if (message.size > 25 * 1024 * 1024) {
      message.setReject("Message too large (>25MB)");
      return;
    }

    try {
      // Extract the user's structurize email (e.g., user123@structurize.ai)
      const toEmail = message.to;
      if (!toEmail.includes('@structurize.ai')) {
        console.log(`Email not sent to structurize domain: ${toEmail}`);
        return; // Ignore emails not sent to structurize domain
      }

      // Determine user from email address
      const userId = await this.getUserIdFromEmail(env.DB, toEmail);
      if (!userId) {
        console.log(`No user found for email: ${toEmail}`);
        return; // Ignore emails for non-existent users
      }

      // Find attachment with supported format (PDF, DOCX, etc.)
      const attachment = this.findSupportedAttachment(message);
      if (!attachment) {
        console.log(`No supported attachment found in email from ${message.from}`);
        return; // Ignore emails without supported attachments
      }

      // Store in R2 with a unique key
      const r2Key = `uploads/${userId}/${crypto.randomUUID()}${this.getExtension(attachment.contentType)}`;
      await env.DOCUMENTS_BUCKET.put(r2Key, attachment.content, {
        httpMetadata: {
          contentType: attachment.contentType,
          contentDisposition: `attachment; filename="${attachment.filename}"`
        },
        customMetadata: {
          originalName: attachment.filename,
          uploadedFrom: message.from,
          emailSubject: message.subject || 'No Subject',
          uploadDate: new Date().toISOString()
        }
      });

      // Determine which extractor to use based on email subject and user's extractors
      const extractorId = await this.getExtractorIdForEmail(env.DB, userId, message.subject);

      // Create job record in database
      const jobId = crypto.randomUUID();
      const job = {
        id: jobId,
        user_id: userId,
        r2_key: r2Key,
        original_name: attachment.filename,
        sender: message.from,
        extractor_id: extractorId || null,
        status: 'pending',
        created_at: Date.now(),
        updated_at: Date.now()
      };

      // Validate job before insertion
      const parsedJob = JobSchema.safeParse(job);
      if (!parsedJob.success) {
        console.error(`Invalid job data: ${parsedJob.error.message}`);
        return;
      }

      // Insert job into database
      await env.DB.prepare(`
        INSERT INTO jobs (id, user_id, r2_key, original_name, sender, extractor_id, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
      `).bind(
        job.id,
        job.user_id,
        job.r2_key,
        job.original_name,
        job.sender,
        job.extractor_id,
        job.status,
        job.created_at,
        job.updated_at
      ).run();

      // Send message to queue for processing
      const queueMessage = {
        jobId: job.id,
        userId: job.user_id,
        extractorId: job.extractor_id
      };

      await env.INGEST_QUEUE.send(queueMessage);
      console.log(`Queued job ${jobId} for user ${userId} with extractor ${extractorId || 'auto'}`);

    } catch (error) {
      console.error('Error processing email:', error);
      // Log to monitoring/observability system
    }
  },

  /**
   * Find a supported attachment in the email (PDF, DOCX, etc.)
   */
  findSupportedAttachment(message: ForwardedEmail): {
    filename: string;
    contentType: string;
    content: ArrayBuffer;
    size: number;
  } | null {
    // This is a simplified representation
    // In a real implementation, you'd properly parse the email with postal-mime
    // and examine all attachments for supported content types

    // Placeholder implementation - in practice you'd use a library
    console.log(`Searching for attachments in email from ${message.from}`);

    // Since we can't actually parse the email content directly in this worker,
    // we assume the Cloudflare Email Routing has already parsed it
    // and we extract what we need from the message object
    // This is a placeholder - in real implementation, you'd use postal-mime or similar
    try {
      // For now, we'll simulate finding an attachment
      // In a real implementation, you'd properly parse the raw email content
      return {
        filename: "sample-attachment.pdf",  // This would come from actual parsing
        contentType: "application/pdf",      // This would come from actual parsing
        content: new ArrayBuffer(0),         // This would be the actual content
        size: 0                              // This would be the actual size
      };
    } catch (e) {
      console.error("Error finding attachment:", e);
      return null;
    }
  },

  /**
   * Get user ID from structurize email address
   */
  async getUserIdFromEmail(db: D1Database, email: string): Promise<string | null> {
    try {
      const result = await db.prepare('SELECT id FROM users WHERE structurize_email = ?').bind(email).first();
      return result ? (result as any).id : null;
    } catch (error) {
      console.error(`Error getting user ID for email ${email}:`, error);
      return null;
    }
  },

  /**
   * Determine extractor ID based on email subject and user's configured extractors
   */
  async getExtractorIdForEmail(db: D1Database, userId: string, subject: string): Promise<string | null> {
    try {
      // Get all extractors for this user
      const extractors = await db.prepare(
        'SELECT id, name, trigger_subject FROM extractors WHERE user_id = ?'
      ).bind(userId).all();

      if (!extractors.results || extractors.results.length === 0) {
        console.log(`No extractors found for user ${userId}, using auto-detection`);
        return null; // Will use auto-detection in the engine
      }

      // Find extractor that matches the subject
      for (const extractor of extractors.results as any[]) {
        if (extractor.trigger_subject && subject.toLowerCase().includes(extractor.trigger_subject.toLowerCase())) {
          console.log(`Matched extractor ${extractor.id} based on subject: ${subject}`);
          return extractor.id;
        }
      }

      // If no specific extractor matched, return null to use auto-detection
      return null;
    } catch (error) {
      console.error(`Error getting extractor for user ${userId} and subject ${subject}:`, error);
      return null;
    }
  },

  /**
   * Get file extension from content type
   */
  getExtension(contentType: string): string {
    switch (contentType) {
      case 'application/pdf':
        return '.pdf';
      case 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
        return '.docx';
      case 'application/msword':
        return '.doc';
      case 'image/jpeg':
        return '.jpg';
      case 'image/png':
        return '.png';
      case 'text/plain':
        return '.txt';
      default:
        return '.dat'; // fallback
    }
  }
} satisfies ExportedHandler<Env>;

// Define the ForwardedEmail interface (this comes from Cloudflare Workers types)
interface ForwardedEmail {
  raw: ReadableStream;
  from: string;
  to: string;
  subject: string;
  size: number;
  [key: string]: any;
}