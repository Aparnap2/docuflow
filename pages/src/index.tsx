import { Hono } from 'hono';
import { html } from 'hono/html';

const app = new Hono();

app.get('/', (c) => c.html(html`
<!DOCTYPE html>
<html>
<head>
  <script src="https://cdn.tailwindcss.com"></script>
  <title>Structurize</title>
</head>
<body class="bg-gradient-to-br from-indigo-50 to-blue-50 min-h-screen">
  <nav class="bg-white shadow-sm border-b">
    <div class="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
      <h1 class="text-2xl font-bold">Structurize</h1>
      <a href="/dashboard" class="bg-indigo-600 text-white px-6 py-2 rounded-lg">Dashboard</a>
    </div>
  </nav>
  <div class="max-w-4xl mx-auto py-16 px-4 text-center">
    <h1 class="text-5xl font-bold text-gray-900 mb-6">Forward emails. Fill spreadsheets.</h1>
    <p class="text-xl text-gray-600 mb-12">Invoice PDFs → Google Sheets automatically</p>
    <div class="bg-white p-8 rounded-2xl shadow-xl max-w-2xl mx-auto">
      <h2 class="text-2xl font-bold mb-6">Your Magic Email</h2>
      <div class="bg-indigo-50 p-6 rounded-xl mb-6">
        <code class="text-2xl font-mono block">user123@structurize.ai</code>
      </div>
      <p class="text-gray-600 mb-8">Forward invoice emails here → Watch data appear in Sheets</p>
      <a href="/dashboard" class="bg-indigo-600 text-white px-8 py-3 rounded-xl font-bold">Open Dashboard</a>
    </div>
  </div>
</body>
</html>
`));

app.get('/dashboard', async (c) => {
  const user = { structurize_email: "user123@structurize.ai", plan: "pro" };
  return c.html(html`
<!DOCTYPE html>
<html>
<head>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-50 min-h-screen">
  <div class="flex">
    <div class="w-64 bg-white border-r p-6">
      <h2 class="text-2xl font-bold mb-8">Structurize</h2>
      <a href="/dashboard" class="block p-3 bg-indigo-50 text-indigo-700 rounded-xl font-bold mb-4">Dashboard</a>
    </div>
    <div class="ml-64 p-8 flex-1">
      <div class="flex justify-between mb-8">
        <h1 class="text-3xl font-bold">Dashboard</h1>
        <div class="flex gap-4 items-center">
          <code class="bg-white border px-4 py-2 rounded-xl text-sm font-mono">${user.structurize_email}</code>
          <span class="bg-indigo-600 text-white px-4 py-2 rounded-xl text-sm font-bold">${user.plan}</span>
        </div>
      </div>
      <div id="jobs" class="bg-white rounded-2xl shadow-sm border p-6">
        <h2 class="text-xl font-bold mb-4">Recent Jobs</h2>
        <div class="space-y-3">
          <div class="flex justify-between p-4 bg-gray-50 rounded-xl">
            <span>aws-invoice.pdf</span>
            <span class="text-green-600 font-bold">✅ Completed</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</body>
</html>
`));
});

export default app;