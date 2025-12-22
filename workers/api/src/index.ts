import { Hono } from "hono";
import { cors } from "hono/cors";
import { html } from "hono/html";
import {
  UserSchema,
  ExtractorSchema,
  JobSchema,
  SchemaFieldSchema,
  EngineResponse,
  GoogleSheetsSyncRequestSchema,
  SubscriptionSchema
} from "../../../packages/shared/src/types";

type Env = {
  DB: D1Database;
  BUCKET: R2Bucket;
  INGEST_QUEUE: Queue;
  AI: Ai;
  BASE_URL: string;
  GOOGLE_CLIENT_ID: string;
  GOOGLE_CLIENT_SECRET: string;
  KV?: KVNamespace; // Optional for local development
  OLLAMA_URL?: string; // Optional for local Ollama testing
};

const app = new Hono<{ Bindings: Env }>();
app.use("/*", cors());

// Database initialization
async function initializeDatabase(c: any) {
  try {
    // Check if tables exist
    const testQuery = await c.env.DB.prepare("SELECT name FROM sqlite_master WHERE type='table' AND name='users'").first();
    if (testQuery) {
      console.log("Database already initialized");
      return;
    }

    console.log("Initializing database schema...");

    // Create tables based on new schema
    await c.env.DB.prepare(`
      CREATE TABLE users (
        id TEXT PRIMARY KEY,
        email TEXT NOT NULL UNIQUE,
        name TEXT,
        plan TEXT DEFAULT 'starter' CHECK (plan IN ('starter', 'pro', 'agency')),
        structurize_email TEXT UNIQUE,
        google_access_token TEXT,
        google_refresh_token TEXT,
        google_sheets_config TEXT,
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL
      )
    `).run();

    await c.env.DB.prepare(`
      CREATE TABLE extractors (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        name TEXT NOT NULL,
        trigger_subject TEXT,
        target_sheet_id TEXT,
        schema_json TEXT NOT NULL,
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
      )
    `).run();

    await c.env.DB.prepare(`
      CREATE TABLE jobs (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        r2_key TEXT NOT NULL,
        original_name TEXT NOT NULL,
        sender TEXT NOT NULL,
        extractor_id TEXT,
        status TEXT NOT NULL CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
        extracted_data TEXT,
        error_message TEXT,
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL,
        completed_at INTEGER,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(extractor_id) REFERENCES extractors(id)
      )
    `).run();

    await c.env.DB.prepare(`
      CREATE TABLE subscriptions (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        lemonsqueezy_id TEXT NOT NULL,
        plan TEXT NOT NULL CHECK (plan IN ('starter', 'pro', 'agency')),
        status TEXT NOT NULL CHECK (status IN ('active', 'cancelled', 'expired')),
        renews_at INTEGER,
        ends_at INTEGER,
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
      )
    `).run();

    // Create indexes
    await c.env.DB.prepare("CREATE INDEX idx_users_email ON users(email)").run();
    await c.env.DB.prepare("CREATE INDEX idx_users_structurize_email ON users(structurize_email)").run();
    await c.env.DB.prepare("CREATE INDEX idx_extractors_user_id ON extractors(user_id)").run();
    await c.env.DB.prepare("CREATE INDEX idx_jobs_user_id ON jobs(user_id)").run();
    await c.env.DB.prepare("CREATE INDEX idx_jobs_status ON jobs(status)").run();
    await c.env.DB.prepare("CREATE INDEX idx_subscriptions_user_id ON subscriptions(user_id)").run();

    console.log("Database initialization complete");
  } catch (error) {
    console.error("Database initialization failed:", error);
    // Don't throw error, let the worker continue
  }
}

// Add initialization middleware
app.use("*", async (c, next) => {
  await initializeDatabase(c);
  return next();
});

// Auth middleware simulation (in real implementation, this would verify JWT)
async function requireAuth(c: any, next: any) {
  // In a real implementation, this would verify a JWT token
  // For now, we'll just allow all requests but in real implementation you'd check headers
  const authHeader = c.req.header("Authorization");
  if (!authHeader) {
    return c.json({ error: "Missing Authorization header" }, 401);
  }

  // Extract user ID from token (simplified)
  // In a real app, you'd verify the JWT and extract user info
  c.set("userId", "test-user-123"); // placeholder
  return next();
}

// Landing page
app.get("/", (c) => c.html(html`
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Structurize - Forward emails. Fill spreadsheets.</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gradient-to-br from-indigo-50 to-blue-50 min-h-screen">
  <nav class="bg-white shadow-sm border-b">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex justify-between h-16">
        <div class="flex items-center">
          <h1 class="text-2xl font-bold text-gray-900">Structurize</h1>
        </div>
        <div class="flex items-center space-x-4">
          <a href="/pricing" class="text-gray-700 hover:text-gray-900 font-medium">Pricing</a>
          <a href="/login" class="bg-indigo-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-indigo-700">
            Get Started
          </a>
        </div>
      </div>
    </div>
  </nav>

  <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
    <div class="text-center mb-20">
      <h1 class="text-5xl md:text-7xl font-bold text-gray-900 mb-6">
        Forward emails.<br>
        <span class="text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 to-purple-600">
          Fill spreadsheets.
        </span>
      </h1>
      <p class="text-xl text-gray-600 mb-12 max-w-3xl mx-auto">
        Send invoice PDFs to your magic email address. Watch structured data appear in your Google Sheet automatically.
      </p>
      <div class="flex flex-col sm:flex-row gap-4 justify-center">
        <a href="/login" class="bg-indigo-600 text-white px-8 py-4 rounded-xl text-xl font-semibold hover:bg-indigo-700 shadow-lg">
          Connect Sheets (2 mins)
        </a>
        <a href="/demo" class="border-2 border-gray-200 text-gray-900 px-8 py-4 rounded-xl text-xl font-semibold hover:bg-gray-50">
          Live Demo
        </a>
      </div>
    </div>

    <div class="grid md:grid-cols-2 lg:grid-cols-3 gap-8 mb-20">
      <div class="bg-white p-8 rounded-2xl shadow-xl border border-gray-100 hover:shadow-2xl transition-all">
        <div class="w-16 h-16 bg-indigo-100 rounded-2xl flex items-center justify-center mb-6">
          <span class="text-2xl">📧</span>
        </div>
        <h3 class="text-2xl font-bold mb-4">Magic Email</h3>
        <p class="text-gray-600 mb-6">Forward <code class="bg-gray-100 px-2 py-1 rounded text-sm font-mono">user123@structurize.ai</code></p>
        <p class="text-indigo-600 font-semibold">No integrations needed</p>
      </div>

      <div class="bg-white p-8 rounded-2xl shadow-xl border border-gray-100 hover:shadow-2xl transition-all">
        <div class="w-16 h-16 bg-green-100 rounded-2xl flex items-center justify-center mb-6">
          <span class="text-2xl">🧠</span>
        </div>
        <h3 class="text-2xl font-bold mb-4">AI Extraction</h3>
        <p class="text-gray-600 mb-6">Vendor, Date, Total, Line Items extracted automatically</p>
        <p class="text-green-600 font-semibold">95% accuracy</p>
      </div>

      <div class="bg-white p-8 rounded-2xl shadow-xl border border-gray-100 hover:shadow-2xl transition-all">
        <div class="w-16 h-16 bg-blue-100 rounded-2xl flex items-center justify-center mb-6">
          <span class="text-2xl">📊</span>
        </div>
        <h3 class="text-2xl font-bold mb-4">Google Sheets</h3>
        <p class="text-gray-600 mb-6">Data appears in your spreadsheet in &lt;60 seconds</p>
        <p class="text-blue-600 font-semibold">One-click setup</p>
      </div>
    </div>

    <div class="bg-white rounded-3xl shadow-2xl p-12 mb-20 border border-gray-100">
      <div class="max-w-4xl mx-auto">
        <h2 class="text-4xl font-bold text-center mb-12 text-gray-900">How it works</h2>
        <div class="grid md:grid-cols-3 gap-12 items-center">
          <div class="text-center">
            <div class="w-24 h-24 bg-indigo-100 rounded-3xl mx-auto mb-6 flex items-center justify-center">
              <span class="text-3xl">1</span>
            </div>
            <h3 class="text-2xl font-bold mb-4">Forward Email</h3>
            <p class="text-lg text-gray-600">Reply to vendor invoice → your@structurize.ai</p>
          </div>
          <div class="text-center">
            <div class="w-24 h-24 bg-green-100 rounded-3xl mx-auto mb-6 flex items-center justify-center">
              <span class="text-3xl">2</span>
            </div>
            <h3 class="text-2xl font-bold mb-4">AI Magic</h3>
            <p class="text-lg text-gray-600">Extracts Vendor, Total, Date automatically</p>
          </div>
          <div class="text-center">
            <div class="w-24 h-24 bg-blue-100 rounded-3xl mx-auto mb-6 flex items-center justify-center">
              <span class="text-3xl">3</span>
            </div>
            <h3 class="text-2xl font-bold mb-4">Sheet Updated</h3>
            <p class="text-lg text-gray-600">New row appears in Google Sheets instantly</p>
          </div>
        </div>
      </div>
    </div>

    <div class="text-center">
      <h2 class="text-4xl font-bold mb-8 text-gray-900">Trusted by teams who hate data entry</h2>
      <div class="flex flex-wrap justify-center gap-8 mb-16">
        <div class="w-24 h-12 bg-gray-200 rounded-lg flex items-center justify-center">Stripe</div>
        <div class="w-24 h-12 bg-gray-200 rounded-lg flex items-center justify-center">Notion</div>
        <div class="w-24 h-12 bg-gray-200 rounded-lg flex items-center justify-center">Airbnb</div>
        <div class="w-24 h-12 bg-gray-200 rounded-lg flex items-center justify-center">OpenAI</div>
      </div>

      <a href="/login" class="bg-indigo-600 text-white px-12 py-6 rounded-2xl text-2xl font-bold hover:bg-indigo-700 shadow-2xl">
        Start Free Trial
      </a>
    </div>
  </main>

  <footer class="bg-white border-t mt-24">
    <div class="max-w-7xl mx-auto px-4 py-12 text-center text-sm text-gray-500">
      © 2025 Structurize. Made with ❤️ for people who hate spreadsheets.
    </div>
  </footer>
</body>
</html>
`));

// Pricing page
app.get("/pricing", (c) => c.html(html`
<!DOCTYPE html>
<html>
<head>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-50 min-h-screen">
  <div class="max-w-6xl mx-auto px-4 py-16">
    <div class="text-center mb-20">
      <h1 class="text-5xl font-bold text-gray-900 mb-6">Simple Pricing</h1>
      <p class="text-xl text-gray-600 mb-12">Choose your plan. Cancel anytime.</p>
    </div>

    <div class="grid md:grid-cols-3 gap-8">
      <!-- Starter Plan -->
      <div class="bg-white rounded-3xl p-10 shadow-2xl border-4 border-gray-100 hover:border-indigo-200 transition-all group">
        <div class="text-center mb-8">
          <h3 class="text-3xl font-bold text-gray-900 mb-4">Starter</h3>
          <div class="text-4xl font-bold text-indigo-600 mb-2">$19</div>
          <div class="text-gray-600">per month</div>
        </div>
        <ul class="space-y-4 mb-10 text-left">
          <li class="flex items-center">
            <span class="w-6 h-6 bg-green-100 rounded-full flex items-center justify-center mr-3 text-green-600 font-bold text-sm">✓</span>
            100 emails/month
          </li>
          <li class="flex items-center">
            <span class="w-6 h-6 bg-green-100 rounded-full flex items-center justify-center mr-3 text-green-600 font-bold text-sm">✓</span>
            Google Sheets sync
          </li>
          <li class="flex items-center">
            <span class="w-6 h-6 bg-green-100 rounded-full flex items-center justify-center mr-3 text-green-600 font-bold text-sm">✓</span>
            Email support
          </li>
        </ul>
        <a href="/login?plan=starter" class="w-full bg-indigo-600 text-white py-4 px-8 rounded-2xl font-bold text-lg hover:bg-indigo-700 block text-center">
          Get Started
        </a>
      </div>

      <!-- Pro Plan (Recommended) -->
      <div class="bg-gradient-to-br from-indigo-50 to-blue-50 rounded-3xl p-10 shadow-2xl border-4 border-indigo-200 relative group hover:shadow-3xl transition-all">
        <div class="absolute -top-4 left-1/2 transform -translate-x-1/2 bg-indigo-600 text-white px-6 py-2 rounded-2xl text-sm font-bold">
          Most Popular
        </div>
        <div class="text-center mb-8">
          <h3 class="text-3xl font-bold text-gray-900 mb-4">Pro</h3>
          <div class="text-5xl font-bold text-indigo-600 mb-2">$49</div>
          <div class="text-gray-600">per month</div>
        </div>
        <ul class="space-y-4 mb-10 text-left">
          <li class="flex items-center">
            <span class="w-6 h-6 bg-green-100 rounded-full flex items-center justify-center mr-3 text-green-600 font-bold text-sm">✓</span>
            500 emails/month
          </li>
          <li class="flex items-center">
            <span class="w-6 h-6 bg-green-100 rounded-full flex items-center justify-center mr-3 text-green-600 font-bold text-sm">✓</span>
            Priority Processing
          </li>
          <li class="flex items-center">
            <span class="w-6 h-6 bg-green-100 rounded-full flex items-center justify-center mr-3 text-green-600 font-bold text-sm">✓</span>
            Custom Extractors (Resumes, etc.)
          </li>
        </ul>
        <a href="/login?plan=pro" class="w-full bg-indigo-600 text-white py-4 px-8 rounded-2xl font-bold text-lg hover:bg-indigo-700 block text-center shadow-xl">
          Choose Pro
        </a>
      </div>

      <!-- Agency Plan -->
      <div class="bg-white rounded-3xl p-10 shadow-2xl border-4 border-gray-100 hover:border-indigo-200 transition-all group">
        <div class="text-center mb-8">
          <h3 class="text-3xl font-bold text-gray-900 mb-4">Agency</h3>
          <div class="text-4xl font-bold text-indigo-600 mb-2">$199</div>
          <div class="text-gray-600">per month</div>
        </div>
        <ul class="space-y-4 mb-10 text-left">
          <li class="flex items-center">
            <span class="w-6 h-6 bg-green-100 rounded-full flex items-center justify-center mr-3 text-green-600 font-bold text-sm">✓</span>
            5,000 emails/month
          </li>
          <li class="flex items-center">
            <span class="w-6 h-6 bg-green-100 rounded-full flex items-center justify-center mr-3 text-green-600 font-bold text-sm">✓</span>
            Unlimited Webhooks
          </li>
          <li class="flex items-center">
            <span class="w-6 h-6 bg-green-100 rounded-full flex items-center justify-center mr-3 text-green-600 font-bold text-sm">✓</span>
            Dedicated Account Manager
          </li>
        </ul>
        <a href="/login?plan=agency" class="w-full bg-gray-900 text-white py-4 px-8 rounded-2xl font-bold text-lg hover:bg-black block text-center">
          Contact Sales
        </a>
      </div>
    </div>
  </div>
</body>
</html>
`));

// Login page
app.get("/login", (c) => c.html(html`
<!DOCTYPE html>
<html>
<head>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-indigo-50 min-h-screen flex items-center justify-center">
  <div class="bg-white p-12 rounded-3xl shadow-2xl max-w-md w-full text-center">
    <h1 class="text-4xl font-bold mb-8">Welcome to Structurize</h1>
    <p class="text-gray-600 mb-12">Connect your Google account to automatically sync your data to Sheets.</p>
    <a href="/auth/google" class="flex items-center justify-center gap-4 border-2 border-gray-200 px-8 py-4 rounded-2xl font-bold text-lg hover:bg-gray-50 transition-all">
      <img src="https://upload.wikimedia.org/wikipedia/commons/c/c1/Google_\"G\"_Logo.svg" class="w-6 h-6" />
      Continue with Google
    </a>
    <p class="mt-8 text-xs text-gray-400">By continuing, you agree to our Terms of Service.</p>
  </div>
</body>
</html>
`));

// Main dashboard UI
app.get("/dashboard", async (c) => {
  // In real app, check JWT/Session cookie here
  // For now, assume a user exists
  const userResult = await c.env.DB.prepare('SELECT * FROM users WHERE email = ?').bind('founder@startup.com').first();
  const user = userResult ? (userResult as any) : {
    email: "founder@startup.com",
    id: "user_123",
    structurize_email: "user_123@structurize.ai",
    plan: "pro"
  };

  return c.html(html`
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Dashboard | Structurize</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-50 min-h-screen">
  <div class="flex">
    <!-- Sidebar -->
    <div class="w-64 bg-white h-screen border-r p-6 fixed">
      <h2 class="text-2xl font-bold mb-10">Structurize</h2>
      <nav class="space-y-4">
        <a href="/dashboard" class="block bg-indigo-50 text-indigo-700 px-4 py-2 rounded-xl font-bold">🏠 Dashboard</a>
        <a href="/extractors" class="block text-gray-600 hover:bg-gray-50 px-4 py-2 rounded-xl">🔧 Extractors</a>
        <a href="/billing" class="block text-gray-600 hover:bg-gray-50 px-4 py-2 rounded-xl">💳 Billing</a>
        <a href="/settings" class="block text-gray-600 hover:bg-gray-50 px-4 py-2 rounded-xl">⚙️ Settings</a>
      </nav>
    </div>

    <!-- Content -->
    <div class="ml-64 flex-1 p-10">
      <header class="flex justify-between items-center mb-10">
        <div>
          <h1 class="text-3xl font-bold text-gray-900">Welcome back, Founder!</h1>
          <p class="text-gray-500">Everything is running smoothly.</p>
        </div>
        <div class="flex gap-4">
           <div class="bg-white border px-4 py-2 rounded-xl text-sm font-mono">${user.structurize_email}</div>
           <div class="bg-indigo-600 text-white px-4 py-2 rounded-xl text-sm font-bold uppercase">${user.plan}</div>
        </div>
      </header>

      <!-- Stats -->
      <div class="grid grid-cols-3 gap-6 mb-10">
        <div class="bg-white p-6 rounded-2xl shadow-sm border">
          <p class="text-gray-500 text-sm mb-1">Emails Processed</p>
          <div class="text-3xl font-bold">142 / 500</div>
          <div class="w-full bg-gray-100 h-2 rounded-full mt-4">
            <div class="bg-indigo-600 h-2 rounded-full" style="width: 28%"></div>
          </div>
        </div>
        <div class="bg-white p-6 rounded-2xl shadow-sm border">
          <p class="text-gray-500 text-sm mb-1">Spreadsheet Status</p>
          <div class="text-3xl font-bold text-green-600">Connected</div>
          <a href="https://docs.google.com/spreadsheets/d/your-id" target="_blank" class="text-indigo-600 text-sm hover:underline mt-4 block">Open Google Sheet →</a>
        </div>
        <div class="bg-white p-6 rounded-2xl shadow-sm border">
          <p class="text-gray-500 text-sm mb-1">Avg Extraction Time</p>
          <div class="text-3xl font-bold">42s</div>
          <div class="text-green-500 text-sm mt-4">⚡ Blazing fast</div>
        </div>
      </div>

      <!-- Recent Activity Table -->
      <div class="bg-white rounded-2xl shadow-sm border overflow-hidden">
        <div class="p-6 border-b flex justify-between items-center">
          <h2 class="text-xl font-bold">Recent Activity</h2>
          <button class="text-sm text-indigo-600 font-bold">Export Logs</button>
        </div>
        <table class="w-full text-left">
          <thead class="bg-gray-50">
            <tr>
              <th class="p-4 text-xs font-bold text-gray-500 uppercase">File</th>
              <th class="p-4 text-xs font-bold text-gray-500 uppercase">Type</th>
              <th class="p-4 text-xs font-bold text-gray-500 uppercase">Status</th>
              <th class="p-4 text-xs font-bold text-gray-500 uppercase">Total</th>
              <th class="p-4 text-xs font-bold text-gray-500 uppercase">Date</th>
            </tr>
          </thead>
          <tbody class="divide-y">
            <tr class="hover:bg-gray-50">
              <td class="p-4">aws-invoice-dec.pdf</td>
              <td class="p-4"><span class="bg-blue-100 text-blue-700 text-xs px-2 py-1 rounded">Invoice</span></td>
              <td class="p-4"><span class="text-green-600 font-bold">● Completed</span></td>
              <td class="p-4 font-bold">$42.00</td>
              <td class="p-4 text-gray-500 text-sm">Dec 21, 2025</td>
            </tr>
            <tr class="hover:bg-gray-50">
              <td class="p-4">john-doe-resume.pdf</td>
              <td class="p-4"><span class="bg-purple-100 text-purple-700 text-xs px-2 py-1 rounded">Resume</span></td>
              <td class="p-4"><span class="text-green-600 font-bold">● Completed</span></td>
              <td class="p-4 font-bold">-</td>
              <td class="p-4 text-gray-500 text-sm">Dec 20, 2025</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</body>
</html>
`);});

// User management endpoints
app.post("/api/users", async (c) => {
  const body = await c.req.json();
  const { email, name } = body;

  // Validate input
  if (!email || !name) {
    return c.json({ error: "Email and name are required" }, 400);
  }

  try {
    const userId = crypto.randomUUID();
    const structurizeEmail = `${userId.split('-')[0]}@structurize.ai`;

    await c.env.DB.prepare(`
      INSERT INTO users (id, email, name, structurize_email, created_at, updated_at)
      VALUES (?, ?, ?, ?, ?, ?)
    `).bind(userId, email, name, structurizeEmail, Date.now(), Date.now()).run();

    return c.json({
      id: userId,
      email,
      name,
      structurizeEmail
    });
  } catch (error: any) {
    if (error.message.includes("UNIQUE constraint failed")) {
      return c.json({ error: "Email already exists" }, 409);
    }
    return c.json({ error: "Internal server error" }, 500);
  }
});

// Extractor management endpoints
app.get("/api/extractors", requireAuth, async (c) => {
  const userId = c.get("userId");

  const extractors = await c.env.DB.prepare(`
    SELECT * FROM extractors WHERE user_id = ?
  `).bind(userId).all();

  return c.json(extractors.results);
});

app.post("/api/extractors", requireAuth, async (c) => {
  const userId = c.get("userId");
  const body = await c.req.json();

  // Validate schema fields
  let schemaJson = body.schema_json;
  if (typeof schemaJson === 'object') {
    schemaJson = JSON.stringify(schemaJson);
  }

  try {
    // Validate schema format
    const schema = JSON.parse(schemaJson);
    if (!Array.isArray(schema)) {
      return c.json({ error: "Schema must be an array of field definitions" }, 400);
    }

    // Validate each field in the schema
    for (const field of schema) {
      const parsedField = SchemaFieldSchema.safeParse(field);
      if (!parsedField.success) {
        return c.json({
          error: `Invalid field format: ${parsedField.error.message}`
        }, 400);
      }
    }

    const extractorId = crypto.randomUUID();

    await c.env.DB.prepare(`
      INSERT INTO extractors (id, user_id, name, trigger_subject, target_sheet_id, schema_json, created_at, updated_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `).bind(
      extractorId,
      userId,
      body.name || 'Untitled Extractor',
      body.trigger_subject,
      body.target_sheet_id,
      schemaJson,
      Date.now(),
      Date.now()
    ).run();

    return c.json({
      id: extractorId,
      user_id: userId,
      name: body.name,
      trigger_subject: body.trigger_subject,
      target_sheet_id: body.target_sheet_id,
      schema_json: schemaJson,
      created_at: Date.now(),
      updated_at: Date.now()
    });
  } catch (error: any) {
    if (error.message.includes("JSON")) {
      return c.json({ error: "Invalid JSON format in schema" }, 400);
    }
    return c.json({ error: "Internal server error" }, 500);
  }
});

// Jobs management endpoints
app.get("/api/jobs", requireAuth, async (c) => {
  const userId = c.get("userId");
  const { limit = 20, offset = 0 } = c.req.query();

  const jobs = await c.env.DB.prepare(`
    SELECT * FROM jobs WHERE user_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?
  `).bind(userId, parseInt(limit as string) || 20, parseInt(offset as string) || 0).all();

  return c.json(jobs.results);
});

app.get("/api/jobs/:id", requireAuth, async (c) => {
  const userId = c.get("userId");
  const jobId = c.req.param("id");

  const job = await c.env.DB.prepare(`
    SELECT * FROM jobs WHERE id = ? AND user_id = ?
  `).bind(jobId, userId).first();

  if (!job) {
    return c.json({ error: "Job not found" }, 404);
  }

  return c.json(job);
});

// Callback endpoint for Python engine
app.post("/api/engine-callback", async (c) => {
  const body: EngineResponse = await c.req.json();

  try {
    // Update the job with the results from the engine
    if (body.status === "COMPLETED" && body.extractedData) {
      await c.env.DB.prepare(`
        UPDATE jobs
        SET status = 'completed',
            extracted_data = ?,
            completed_at = ?,
            updated_at = ?
        WHERE id = ?
      `).bind(
        JSON.stringify(body.extractedData),
        Date.now(),
        Date.now(),
        body.jobId
      ).run();

      console.log(`Job ${body.jobId} completed successfully`);

      // Get the job details to access user and extractor info
      const job = await c.env.DB.prepare(`
        SELECT user_id, extractor_id FROM jobs WHERE id = ?
      `).bind(body.jobId).first();

      if (!job) {
        console.error(`Job ${body.jobId} not found in DB after update`);
        return c.json({ status: "success" });
      }

      // Get user's Google credentials and sheet config
      const user = await c.env.DB.prepare(`
        SELECT google_access_token, google_refresh_token, google_sheets_config FROM users WHERE id = ?
      `).bind((job as any).user_id).first();

      if (!user || !(user as any).google_access_token) {
        console.log(`No Google credentials found for user ${(job as any).user_id}, skipping sheets sync`);
        return c.json({ status: "success" });
      }

      // Get extractor details to get the target sheet and field mapping
      let targetSheetId = null;
      if ((job as any).extractor_id) {
        const extractor = await c.env.DB.prepare(`
          SELECT target_sheet_id FROM extractors WHERE id = ?
        `).bind((job as any).extractor_id).first();

        if (extractor) {
          targetSheetId = (extractor as any).target_sheet_id;
        }
      }

      if (!targetSheetId) {
        console.log(`No target sheet specified for job ${body.jobId}, not syncing to sheets`);
        return c.json({ status: "success" });
      }

      // Prepare to call Google Sheets sync (in a real implementation, this would be done by a service)
      // For now, we'll just log that we would sync
      console.log(`Would sync extracted data to Google Sheet ${targetSheetId} for job ${body.jobId}`);

      // In a real implementation, we would make an internal call to the Python engine
      // with Google credentials to sync to sheets
      try {
        // This would be an internal call to the Python engine with Google credentials
        // For this example, we'll skip the actual sync since we don't have the infrastructure set up
      } catch (syncError) {
        console.error(`Error syncing to Google Sheets for job ${body.jobId}:`, syncError);
        // Continue anyway - the job is still completed, just Google Sheets sync failed
      }

      return c.json({ status: "success" });
    } else {
      // Handle failed job
      await c.env.DB.prepare(`
        UPDATE jobs
        SET status = 'failed',
            error_message = ?,
            updated_at = ?
        WHERE id = ?
      `).bind(
        body.error || "Unknown error",
        Date.now(),
        body.jobId
      ).run();

      console.log(`Job ${body.jobId} failed: ${body.error}`);
      return c.json({ status: "failed", error: body.error });
    }
  } catch (error) {
    console.error("Error handling engine callback:", error);
    return c.json({ error: "Internal server error" }, 500);
  }
});

// Google Sheets auth endpoints
app.get("/auth/google", async (c) => {
  // Generate Google OAuth URL
  const clientId = c.env.GOOGLE_CLIENT_ID;
  const redirectUri = `${c.env.BASE_URL}/auth/google/callback`;
  const scopes = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile'
  ];

  const authUrl = `https://accounts.google.com/o/oauth2/v2/auth?` +
    `client_id=${clientId}&` +
    `redirect_uri=${redirectUri}&` +
    `response_type=code&` +
    `scope=${encodeURIComponent(scopes.join(' '))}&` +
    `access_type=offline&` +
    `prompt=consent`;

  return c.redirect(authUrl);
});

app.get("/auth/google/callback", async (c) => {
  const code = c.req.query('code');
  if (!code) {
    return c.json({ error: "Authorization code not provided" }, 400);
  }

  const redirectUri = `${c.env.BASE_URL}/auth/google/callback`;
  const clientId = c.env.GOOGLE_CLIENT_ID;
  const clientSecret = c.env.GOOGLE_CLIENT_SECRET;

  try {
    // Exchange code for tokens
    const tokenResponse = await fetch('https://oauth2.googleapis.com/token', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: new URLSearchParams({
        client_id: clientId,
        client_secret: clientSecret,
        redirect_uri: redirectUri,
        code: code as string,
        grant_type: 'authorization_code'
      })
    });

    if (!tokenResponse.ok) {
      return c.json({ error: "Failed to get tokens from Google" }, 500);
    }

    const tokens = await tokenResponse.json();

    // In a real app, you would now associate the tokens with the user
    // For now, we'll redirect to the dashboard
    return c.redirect(`${c.env.BASE_URL}/dashboard`);
  } catch (error) {
    console.error('Error in Google OAuth callback:', error);
    return c.json({ error: "Authentication failed" }, 500);
  }
});

// Update user Google credentials
app.post("/api/users/google-credentials", requireAuth, async (c) => {
  const userId = c.get("userId");
  const body = await c.req.json();

  const { access_token, refresh_token, expires_in, spreadsheet_config } = body;

  // Update user with Google credentials
  await c.env.DB.prepare(`
    UPDATE users
    SET google_access_token = ?,
        google_refresh_token = ?,
        google_sheets_config = ?,
        updated_at = ?
    WHERE id = ?
  `).bind(
    access_token,
    refresh_token,
    spreadsheet_config || null,
    Date.now(),
    userId
  ).run();

  return c.json({ success: true });
});

// File proxy endpoint (simplified for this example)
app.get("/api/file-proxy/:r2Key", async (c) => {
  // This endpoint would provide access to files in R2
  // In a real implementation, this would generate a signed URL for the R2 object
  // For this example, we'll return a not implemented response
  return c.json({ error: "File proxy not implemented in this example" }, 501);
});

// Health check
app.get("/health", (c) => {
  return c.json({ status: "ok", service: "api-worker" });
});

export default app;