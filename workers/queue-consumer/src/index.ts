/**
 * Queue Consumer Worker for Docuflow
 * Processes documents from the queue and sends them to the Python engine
 */

import { QueueJobSchema } from '@docuflow/shared';

interface Env {
  // Queue for processing documents
  DOCUMENT_QUEUE: Queue<any>;
  
  // Dead letter queue for failed messages
  DLQ_QUEUE: Queue<any>;
  
  // Python engine URL
  PYTHON_ENGINE_URL: string;
  
  // Webhook secret for authenticating with the Python engine
  PYTHON_ENGINE_SECRET: string;
  
  // Web URL for callbacks
  WEB_URL: string;
  
  // Internal secrets
  WEBHOOK_SECRET: string;
}

// Define the message interface as per PRD
interface QueueJob {
  docId: string;
  workspaceId: string;
}

export default {
  async queue(batch: MessageBatch<QueueJob>, env: Env): Promise<void> {
    console.log(`Processing batch of ${batch.messages.length} messages`);
    
    // Process all messages in the batch
    const promises = batch.messages.map(async (message) => {
      try {
        // Validate message format
        const parsedMessage = QueueJobSchema.safeParse(message.body);
        if (!parsedMessage.success) {
          console.error(`Invalid queue message: ${parsedMessage.error.message}`);
          // Permanent error: acknowledge to discard
          message.ack();
          return;
        }
        
        const { docId, workspaceId } = parsedMessage.data;
        
        console.log(`Processing document ${docId} for workspace ${workspaceId}`);
        
        // Call the Python engine with the correct payload format as per PRD
        const callbackUrl = `${env.WEB_URL}/api/webhook/engine`;
        const fileProxy = `${env.WEB_URL}/api/proxy/${docId}`;
        
        const requestBody = {
          doc_id: docId,
          workspace_id: workspaceId,
          callback_url: callbackUrl,
          file_proxy: fileProxy
        };
        
        // Fire-and-forget approach to prevent timeout on large files
        // Python Engine will process asynchronously and send callback
        fetch(env.PYTHON_ENGINE_URL, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${env.PYTHON_ENGINE_SECRET}`,
          },
          body: JSON.stringify(requestBody)
        })
        .then(response => {
          if (!response.ok) {
            console.error(`Python engine error for ${docId}: ${response.status} ${response.statusText}`);
            // Only log error, don't throw - queue consumer should not wait for response
          } else {
            console.log(`Successfully sent document ${docId} to Python engine`);
          }
        })
        .catch(error => {
          console.error(`Network error sending document ${docId} to Python engine:`, error);
          // Log error but don't throw to prevent queue consumer timeout
        });
        
        console.log(`Successfully sent document ${docId} to Python engine`);
        // Message will be automatically acknowledged if no exception is thrown
      } catch (error) {
        console.error(`Error processing message for document ${message.body.docId}:`, error);
        // Exponential Backoff: 2^attempts seconds (as specified in PRD)
        const delay = Math.pow(2, message.attempts);
        console.log(`Retrying in ${delay}s`);
        message.retry({ delaySeconds: delay });
      }
    });
    
    // Wait for all messages to be processed
    await Promise.all(promises);
  }
} satisfies ExportedHandler<Env> & QueueConsumer<QueueJob>;