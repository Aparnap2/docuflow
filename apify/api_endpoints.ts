import { Hono } from 'hono';
import { drizzle } from 'drizzle-orm/d1';
import { googleAuth } from '@hono/oauth-providers/google';
import { users } from './db/schema';
import { cors } from 'hono/cors';

type Bindings = {
  DB: D1Database
  GOOGLE_CLIENT_ID: string
  GOOGLE_CLIENT_SECRET: string
  JWT_SECRET: string
  APIFY_TOKEN: string
  APIFY_ACTOR_ID: string
  API_URL: string
}

const app = new Hono<{ Bindings: Bindings }>();

// Enable CORS for all routes
app.use('*', cors());

// Health check endpoint
app.get('/health', (c) => {
  return c.json({ status: 'ok', timestamp: Date.now() });
});

// Main API endpoint
app.get('/', (c) => {
  return c.html(`
    <!DOCTYPE html>
    <html>
    <head>
      <title>Sarah AI - Configurable Digital Intern</title>
      <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-100">
      <div class="container mx-auto p-8">
        <h1 class="text-3xl font-bold mb-6">Sarah AI - The Configurable Digital Intern</h1>
        <p class="text-lg mb-6">Turn messy emails (PDFs) into perfect, user-defined CSVs/Sheets.</p>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div class="bg-white p-6 rounded-lg shadow">
            <h2 class="text-xl font-bold mb-4">Authentication</h2>
            <a href="/auth/google" class="bg-red-500 hover:bg-red-600 text-white py-2 px-4 rounded">Sign in with Google</a>
          </div>
          <div class="bg-white p-6 rounded-lg shadow">
            <h2 class="text-xl font-bold mb-4">Blueprint Builder</h2>
            <a href="/blueprints/new" class="bg-blue-500 hover:bg-blue-600 text-white py-2 px-4 rounded">Create New Blueprint</a>
          </div>
        </div>
      </div>
    </body>
    </html>
  `);
});

// 1. Auth Middleware & Routes
app.use('/auth/google', googleAuth({
  scope: ['profile', 'email'],
}));

app.get('/auth/google/callback', async (c) => {
  const user = c.get('user') as { email: string; id: string }; // From googleAuth middleware
  const db = drizzle(c.env.DB);

  // Upsert User
  const [dbUser] = await db.insert(users).values({
    id: crypto.randomUUID(),
    email: user.email,
    google_id: user.id
  }).onConflictDoUpdate({ 
    target: users.email, 
    set: { google_id: user.id } 
  }).returning();

  // Set a simple session cookie (in a real app, you'd use proper JWT)
  c.header('Set-Cookie', `user_id=${dbUser.id}; Path=/; HttpOnly; SameSite=Strict`);
  
  return c.redirect('/dashboard');
});

// Import API routes
import blueprintsApi from './api/blueprints';
import jobsApi from './api/jobs';
import webhooksApi from './api/webhooks';

// API routes with authentication
app.route('/blueprints', blueprintsApi);
app.route('/jobs', jobsApi);
app.route('/webhook', webhooksApi);

// Apify-specific endpoints
app.post('/webhook/apify-result', async (c) => {
  try {
    const payload = await c.req.json();
    
    // Verify webhook signature if needed
    // This would depend on how Apify sends the webhook
    
    const { jobId, result } = payload;
    
    // Update the job in the database with the results from Apify
    const db = drizzle(c.env.DB);
    
    await db.update(jobs).set({
      status: result.validation_status === 'valid' ? 'completed' : 'review',
      result_json: JSON.stringify(result),
      confidence: result.confidence || 0.0,
      completed_at: new Date()
    }).where(eq(jobs.id, jobId));
    
    // If the job has a low confidence, trigger a review process
    if ((result.confidence || 0) < 0.8) {
      // In a real implementation, you would trigger a review notification
      console.log(`Job ${jobId} requires review due to low confidence`);
    }
    
    // Send completion notification to internal webhook
    try {
      await fetch(`${c.env.API_URL}/webhook/internal/complete`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-internal-secret': c.env.WORKER_API_SECRET
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
    
    return c.json({ success: true });
  } catch (error) {
    console.error('Error handling Apify webhook:', error);
    return c.json({ success: false, error: error.message }, 500);
  }
});

// Endpoint to trigger Apify processing directly
app.post('/process-with-apify', async (c) => {
  const { pdf_url, schema, job_id } = await c.req.json();
  
  if (!pdf_url || !schema) {
    return c.json({ error: 'pdf_url and schema are required' }, 400);
  }
  
  try {
    // Call Apify API to trigger the actor
    const response = await fetch(`https://api.apify.com/v2/acts/${c.env.APIFY_ACTOR_ID}/runs?token=${c.env.APIFY_TOKEN}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        pdf_url,
        schema,
        job_id: job_id || null,
        webhookUrl: `${c.env.API_URL}/webhook/apify-result` // Endpoint to receive results
      })
    });
    
    if (!response.ok) {
      console.error(`Failed to trigger Apify actor: ${response.status} ${response.statusText}`);
      return c.json({ error: 'Failed to trigger Apify processing' }, 500);
    }
    
    const result = await response.json();
    
    // Update job with Apify run ID
    if (job_id) {
      const db = drizzle(c.env.DB);
      await db.update(jobs).set({
        apify_run_id: result.id,
        status: 'processing'
      }).where(eq(jobs.id, job_id));
    }
    
    return c.json({
      success: true,
      apify_run_id: result.id,
      message: 'Processing started in Apify'
    });
  } catch (error) {
    console.error('Error triggering Apify actor:', error);
    return c.json({ error: error.message }, 500);
  }
});

export default app;