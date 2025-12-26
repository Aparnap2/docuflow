export default {
  async queue(batch: any, env: any, ctx: any) {
    const MAX_RETRY_ATTEMPTS = 5; // Maximum number of retry attempts before dead-lettering

    for (const message of batch.messages) {
      try {
        const { jobId, userId, r2Key, blueprintId, schema_json } = message.body;

        console.log(`Processing job ${jobId} for user ${userId}, attempt ${message.attempts}, blueprint: ${blueprintId}`);

        // Fetch job details from the database
        const job = await env.DB.prepare(`
          SELECT id, user_id, status, r2_key, result_json, confidence, created_at, completed_at
          FROM jobs
          WHERE id = ?
        `).bind(jobId).first();

        if (!job) {
          console.log(`Job ${jobId} not found, acknowledging message`);
          message.ack();
          continue;
        }

        // This worker now handles results from Apify instead of processing directly
        // The actual processing happens in the Apify actor
        // This worker now just handles the webhook from Apify
        
        // In a real implementation, this worker would be triggered by a webhook from Apify
        // when the actor completes processing
        
        message.ack();
        console.log(`Successfully processed job ${jobId}`);

      } catch (error) {
        console.error(`Sync failed for job ${jobId}, user ${userId}, attempt ${message.attempts}:`, error);

        // Check if we've exceeded max retry attempts
        if (message.attempts >= MAX_RETRY_ATTEMPTS) {
          console.error(`Max retry attempts (${MAX_RETRY_ATTEMPTS}) reached for job ${jobId}. Moving to dead letter.`);

          try {
            // Update job status to 'failed' in the database
            await env.DB.prepare(`
              UPDATE jobs SET
                status = ?, completed_at = ?
              WHERE id = ?
            `).bind('failed', Date.now(), message.body.jobId).run();
          } catch (updateError) {
            console.error(`Failed to update job status to 'failed' for job ${message.body.jobId}:`, updateError);
          }

          // Acknowledge the message to prevent further retries
          message.ack();
        } else {
          // Retry with exponential backoff, capped at 300 seconds (5 minutes)
          const delay = Math.min(300, Math.pow(2, message.attempts));
          console.log(`Retrying job ${message.body.jobId} in ${delay} seconds`);
          message.retry(delay);
        }
      }
    }
  }
};

// Webhook handler for Apify results
export async function handleApifyWebhook(request: Request, env: any) {
  try {
    const payload = await request.json();
    
    // Verify webhook signature if needed
    // This would depend on how Apify sends the webhook
    
    const { jobId, result } = payload;
    
    // Update the job in the database with the results from Apify
    await env.DB.prepare(`
      UPDATE jobs
      SET status = ?, result_json = ?, confidence = ?, completed_at = ?
      WHERE id = ?
    `).bind(
      result.validation_status === 'valid' ? 'completed' : 'review',
      JSON.stringify(result),
      result.confidence || 0.0,
      Date.now(),
      jobId
    ).run();

    // If the job has a low confidence, trigger a review process
    if (result.confidence < 0.8) {
      // Send notification to user for review
      await triggerReviewNotification(env, jobId, result);
    }

    // Send completion notification to the main API
    try {
      await fetch(`${env.API_URL}/webhook/internal/complete`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-internal-secret': env.WORKER_API_SECRET
        },
        body: JSON.stringify({
          job_id: jobId,
          status: result.validation_status === 'valid' ? 'completed' : 'review',
          result: result,
          confidence: result.confidence || 0.0
        })
      });
      console.log(`Internal callback sent for job ${jobId}`);
    } catch (callbackError) {
      console.error(`Failed to send internal callback for job ${jobId}:`, callbackError);
    }

    return new Response(JSON.stringify({ success: true }), {
      headers: { 'Content-Type': 'application/json' }
    });
  } catch (error) {
    console.error('Error handling Apify webhook:', error);
    return new Response(JSON.stringify({ success: false, error: error.message }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}

// Helper function to trigger review notification
async function triggerReviewNotification(env: any, jobId: string, result: any) {
  // Find the job to get user information
  const job = await env.DB.prepare(`
    SELECT j.id, j.user_id, u.email
    FROM jobs j
    JOIN users u ON j.user_id = u.id
    WHERE j.id = ?
  `).bind(jobId).first();

  if (!job) {
    console.error(`Job ${jobId} not found for review notification`);
    return;
  }

  // In a real implementation, you would send an email or notification to the user
  // to review the extracted data
  console.log(`Sending review notification to user ${job.user_id} for job ${jobId}`);
}