/**
 * Email Ingest Worker for Docuflow
 * Processes incoming emails, extracts attachments (PDF, JPG, PNG), and stores them in R2
 */

import { QueueJobSchema } from '@docuflow/shared';

// Define the environment bindings for Cloudflare Workers
interface Env {
  // R2 Bucket for storing documents
  DOCUMENTS_BUCKET: R2Bucket;
  
  // Queue for processing documents
  DOCUMENT_QUEUE: Queue<any>;
  
  // Rate limiting namespace
  RATE_LIMITER: RateLimit;
  
  // Database connection
  DATABASE_URL: string;
  DIRECT_URL: string;
  
  // Auth secrets
  AUTH_SECRET: string;
  GOOGLE_CLIENT_ID: string;
  GOOGLE_CLIENT_SECRET: string;
  
  // Internal API
  WEB_API_URL: string;
  INTERNAL_SECRET: string;
}

export interface EmailData {
  from: string;
  to: string;
  subject: string;
  date: string;
  text: string;
  html: string;
  attachments: Array<{
    filename: string;
    contentType: string;
    content: ArrayBuffer;
    size: number;
  }>;
}

export interface EmailMessage {
  rawEmail: string;
  emailData: EmailData;
  userId?: string; // Will be determined from sender or email content
}

export default {
  async email(message: ForwardedEmail, env: Env, ctx: ExecutionContext): Promise<void> {
    // Validate size (25MB limit for Cloudflare Workers)
    if (message.size > 25 * 1024 * 1024) {
      message.setReject("Message too large (>25MB)");
      return;
    }

    try {
      // Parse the email using a library like PostalMime
      // Note: In a real implementation, you'd use a library like postal-mime
      // For this example, we'll assume the email is already parsed
      const raw = await new Response(message.raw).arrayBuffer();
      
      // Determine the attachment from the email (simplified)
      // In practice, you'd use a proper email parsing library
      // This is a simplified representation
      
      // Find attachment with supported format (PDF, JPG, PNG)
      // This is a simplified implementation - in reality you'd use postal-mime
      const attachment = this.findSupportedAttachment(message);
      if (!attachment) {
        console.log(`No supported attachment found in email from ${message.from}`);
        return; // Ignore emails without supported attachments
      }

      // Store in R2 with a unique key
      const r2Key = `inbound/${crypto.randomUUID()}${this.getExtension(attachment.contentType)}`;
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

      // Call web API to create DB row (to avoid bundling Prisma in email worker)
      const res = await fetch(`${env.WEB_API_URL}/api/internal/ingest`, {
        method: 'POST',
        headers: { 
          'x-secret': env.INTERNAL_SECRET,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          r2Key,
          originalName: attachment.filename,
          sender: message.from
        })
      });

      if (!res.ok) {
        throw new Error(`Failed to create document row: ${await res.text()}`);
      }
      
      const { docId, workspaceId } = await res.json();

      // Send message to queue with correct format as per PRD
      const queueMessage = {
        docId,
        workspaceId,
      };
      
      // Validate the message against the schema
      const parsedMessage = QueueJobSchema.safeParse(queueMessage);
      if (!parsedMessage.success) {
        console.error(`Invalid queue message: ${parsedMessage.error.message}`);
        return;
      }
      
      await env.DOCUMENT_QUEUE.send(parsedMessage.data);
      console.log(`Queued document ${docId} for workspace ${workspaceId}`);
      
    } catch (error) {
      console.error('Error processing email:', error);
      // Log to monitoring/observability system
    }
  },

  /**
   * Find a supported attachment in the email (PDF, JPG, PNG)
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
    
    // Return null for now since we can't actually parse the email without a library
    // This would be implemented with postal-mime in a real scenario
    return null;
  },

  /**
   * Get file extension from content type
   */
  getExtension(contentType: string): string {
    switch (contentType) {
      case 'application/pdf':
        return '.pdf';
      case 'image/jpeg':
        return '.jpg';
      case 'image/png':
        return '.png';
      default:
        return '.dat'; // fallback
    }
  }
} satisfies ExportedHandler<Env>;

// Define the ForwardedEmail interface (this would come from Cloudflare Workers types)
interface ForwardedEmail {
  raw: ReadableStream;
  from: string;
  to: string;
  subject: string;
  size: number;
  [key: string]: any;
}