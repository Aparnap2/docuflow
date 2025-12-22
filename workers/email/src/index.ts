import PostalMime from 'postal-mime';

export default {
  async email(message: any, env: any, ctx: any) {
    try {
      const raw = await new Response(message.raw as ReadableStream).arrayBuffer();
      const parser = new PostalMime();
      const email = await parser.parse(raw as ArrayBuffer);
      
      const attachment = email.attachments?.find((a: any) => 
        a.contentType?.startsWith('application/pdf')
      );
      
      if (!attachment) {
        console.log('No PDF attachment, skipping');
        return;
      }

      const recipient = message.to[0].address;
      const userId = recipient.split('@')[0];
      
      const user = await env.DB.prepare(
        'SELECT id FROM users WHERE structurize_email = ?'
      ).bind(userId).first();
      
      if (!user) {
        console.log('Unknown user:', userId);
        return;
      }

      const r2Key = `inbox/${userId}/${Date.now()}.pdf`;
      await env.INBOX_BUCKET.put(r2Key, attachment.content, {
        httpMetadata: { contentType: attachment.contentType }
      });

      const jobId = crypto.randomUUID();
      await env.DB.prepare(`
        INSERT INTO jobs (id, user_id, r2_key, status, created_at)
        VALUES (?, ?, ?, 'pending', ?)
      `).bind(jobId, userId, r2Key, Date.now()).run();

      await env.JOBS_QUEUE.send({ jobId, userId, r2Key });
      
      console.log(`Job queued: ${jobId}`);
      
    } catch (error) {
      console.error('Email processing failed:', error);
    }
  }
};