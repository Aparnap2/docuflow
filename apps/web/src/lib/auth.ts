import { betterAuth } from 'better-auth';
import { prismaAdapter } from '@better-auth/prisma-adapter';
import { db } from '@docuflow/database';

export const auth = betterAuth({
  database: prismaAdapter(db.getClient(), {
    provider: 'postgresql',
  }),
  socialProviders: {
    google: {
      clientId: process.env.GOOGLE_CLIENT_ID!,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
    },
  },
  emailAndPassword: {
    enabled: true,
    requireEmailVerification: false,
  },
  account: {
    accountModel: {
      createPrimary: true,
    },
  },
  secret: process.env.AUTH_SECRET || 'fallback-secret-for-development',
  trustHost: true,
  baseURL: process.env.AUTH_BASE_URL || 'http://localhost:5173',
  emails: {
    config: {
      from: process.env.AUTH_EMAIL_FROM || 'noreply@example.com',
    },
  },
});

// Re-export types for easier access
export type { Session, User } from 'better-auth/types';