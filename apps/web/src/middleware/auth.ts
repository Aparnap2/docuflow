import { auth } from '../lib/auth';
import { Context } from 'hono';

export const withAuth = async (c: Context, next: () => Promise<void>) => {
  // Get the auth request from Hono context
  const authRequest = auth.handleRequest({
    request: c.req.raw,
    env: { 
      // In Cloudflare Workers, we access environment variables through c.env
      // For local development, these will come from process.env
      AUTH_SECRET: c.env?.AUTH_SECRET || process.env.AUTH_SECRET,
      AUTH_BASE_URL: c.env?.AUTH_BASE_URL || process.env.AUTH_BASE_URL,
      DATABASE_URL: c.env?.DATABASE_URL || process.env.DATABASE_URL,
      GOOGLE_CLIENT_ID: c.env?.GOOGLE_CLIENT_ID || process.env.GOOGLE_CLIENT_ID,
      GOOGLE_CLIENT_SECRET: c.env?.GOOGLE_CLIENT_SECRET || process.env.GOOGLE_CLIENT_SECRET,
    }
  });

  // Get the current session
  const session = await authRequest.getSession();
  
  // Add session to context for use in route handlers
  c.set('session', session);
  c.set('user', session?.user || null);

  await next();
};

// Type declarations for the added context properties
declare module 'hono' {
  interface ContextVariableMap {
    session: any;
    user: any;
  }
}

export const requireAuth = async (c: Context, next: () => Promise<void>) => {
  await withAuth(c, async () => {
    const session = c.get('session');
    if (!session) {
      return c.json({ error: 'Authentication required' }, 401);
    }
    await next();
  });
};