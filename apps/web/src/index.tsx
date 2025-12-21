import { Hono } from 'hono';
import { db } from './lib/db';

// Comment out production-ready auth for now to focus on testing
// import { betterAuth } from "better-auth";
// import { hono } from "better-auth/hono";

// const auth = betterAuth({
//   app: {
//     name: "DocuFlow",
//     baseUrl: "http://localhost:8787",
//   },
//   database: {
//     url: process.env.DATABASE_URL!,
//     provider: "postgresql",
//   },
//   emailAndPassword: {
//     enabled: true,
//   },
//   socialProviders: {
//     google: {
//       clientId: process.env.GOOGLE_CLIENT_ID!,
//       clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
//     },
//   },
// });

type Env = {
  Bindings: {
    DOCS_BUCKET: R2Bucket;
    WEBHOOK_SECRET: string;
    DATABASE_URL: string;
    // Comment out for testing
    // ...auth.fetch.context
  }
};

const app = new Hono<Env>();

// Comment out the full auth middleware for testing
// app.use('*', hono(auth));

// --- Health check ---
app.get('/health', (c) => {
  return c.json({ status: 'ok' });
});

// --- Simple test auth endpoint ---
app.get('/api/auth/test', async (c) => {
  // For testing purposes, we'll use a simple header-based auth
  // In production, this will be replaced with proper session management
  const authHeader = c.req.header('Authorization');
  
  if (authHeader !== 'Bearer test-token') {
    return c.json({ error: 'Unauthorized' }, 401);
  }
  
  return c.json({ message: 'Authenticated successfully', user: { id: 'test-user', email: 'test@example.com' } });
});

// --- UI Routes ---
app.get('/dashboard', async (c) => {
  // For testing, we'll use a simple header check
  // In production, this will use proper sessions
  const authHeader = c.req.header('Authorization');
  if (authHeader !== 'Bearer test-token') {
    return c.html('<h1>Access Denied - Use Authorization: Bearer test-token</h1>');
  }

  // MVP: Hardcoded workspace for demo. In prod, get from Auth Cookie/Header
  const workspaceId = "default-ws";

  // For testing, we'll return a simple HTML page
  // In production, this will use Prisma with RLS
  return c.html(`
    <!DOCTYPE html>
    <html>
      <head>
        <title>DocuFlow Dashboard</title>
        <script src="https://cdn.tailwindcss.com"></script>
      </head>
      <body class="p-8 bg-gray-50">
        <div class="max-w-6xl mx-auto">
          <header class="mb-8">
            <h1 class="text-3xl font-bold text-gray-900">DocuFlow Dashboard</h1>
            <p class="text-gray-600">Document Processing System</p>
          </header>
          
          <div class="bg-white shadow rounded p-6 mb-6">
            <h2 class="text-xl font-semibold mb-4">Upload Document</h2>
            <form id="uploadForm" class="space-y-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Document</label>
                <input type="file" name="document" accept=".pdf,.doc,.docx,.jpg,.jpeg,.png" class="w-full border border-gray-300 rounded px-3 py-2">
              </div>
              <button type="submit" class="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">
                Upload and Process
              </button>
            </form>
          </div>
          
          <div class="bg-white shadow rounded p-6">
            <h2 class="text-xl font-semibold mb-4">Recent Documents</h2>
            <div class="overflow-x-auto">
              <table class="w-full text-left">
                <thead>
                  <tr class="border-b">
                    <th class="p-2 text-left">Document</th>
                    <th class="p-2 text-left">Status</th>
                    <th class="p-2 text-left">Vendor</th>
                    <th class="p-2 text-left">Amount</th>
                    <th class="p-2 text-left">Date</th>
                  </tr>
                </thead>
                <tbody id="documentsTable">
                  <tr class="border-b">
                    <td class="p-2">invoice_sample.pdf</td>
                    <td class="p-2"><span class="px-2 py-1 rounded text-xs bg-green-100 text-green-800">Completed</span></td>
                    <td class="p-2">ACME Corporation</td>
                    <td class="p-2">$7,700.00</td>
                    <td class="p-2">2023-08-15</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
        
        <script>
          document.getElementById('uploadForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            alert('Document upload would be processed in the full implementation');
          });
        </script>
      </body>
    </html>
  `);
});

// --- API: Proxy File to Engine (Secure) ---
app.get('/api/proxy/:docId', async (c) => {
  const docId = c.req.param('docId');
  const secret = c.req.header('x-secret');
  if (secret !== c.env.WEBHOOK_SECRET) return c.text('Unauthorized', 401);

  // For testing, return a mock response
  // In production, this would retrieve from R2 bucket
  return c.text('Mock PDF content for testing', 200, {
    'Content-Type': 'application/pdf',
    'Content-Disposition': 'attachment; filename="test.pdf"'
  });
});

// --- API: Engine Callback ---
app.post('/api/webhook/engine', async (c) => {
  const secret = c.req.header('x-secret');
  if (secret !== c.env.WEBHOOK_SECRET) return c.text('Unauthorized', 401);

  const body = await c.req.json();
  // Validate using shared schema (would be uncommented in production)
  // const payload = EngineCallbackSchema.parse(body);
  
  const docId = c.req.query('docId'); // Passed in URL by Consumer

  console.log('Engine callback received for docId:', docId, 'with payload:', body);

  // For testing, just acknowledge the callback
  // In production, this would update the database via Prisma with RLS
  return c.json({ ok: true, docId, received: body.status });
});

// --- API: Document upload (placeholder for testing) ---
app.post('/api/documents/upload', async (c) => {
  const authHeader = c.req.header('Authorization');
  if (authHeader !== 'Bearer test-token') {
    return c.json({ error: 'Unauthorized' }, 401);
  }

  // For testing, just acknowledge the upload
  // In production, this would store in R2 and create DB record
  return c.json({ 
    ok: true, 
    docId: 'test-doc-' + Date.now(),
    status: 'uploaded_for_processing' 
  });
});

export default app;