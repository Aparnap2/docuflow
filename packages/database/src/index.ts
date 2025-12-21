import { PrismaClient } from "@prisma/client";

// For local testing, use regular Prisma client with url
// For production edge, use adapter or accelerate
const prisma = new PrismaClient({
  datasourceUrl: process.env.DATABASE_URL
});

export const db = {
  // Enforces RLS via Session Variable
  async withRLS<T>(workspaceId: string, fn: (tx: any) => Promise<T>) {
    return prisma.$transaction(async (tx) => {
      await tx.$executeRawUnsafe(
        `SELECT set_config('app.current_workspace_id', $1, true)`,
        workspaceId
      );
      return fn(tx);
    });
  },
  // Bypasses RLS (Use with caution for system tasks)
  async sudo<T>(fn: (tx: any) => Promise<T>) {
      return fn(prisma);
  },
  // Get the PrismaClient instance for adapters (e.g., Better Auth)
  getClient: () => prisma
};

// Also export the raw client for advanced usage
export { prisma };