/**
 * Prisma Client Instance
 * Singleton pattern to prevent multiple instances in development
 */

import { PrismaClient } from '@prisma/client';
import { logger } from '../utils/logger';

declare global {
  var prisma: PrismaClient | undefined;
}

export const prisma = global.prisma || new PrismaClient({
  log: process.env.NODE_ENV === 'development' 
    ? ['query', 'error', 'warn'] 
    : ['error'],
});

if (process.env.NODE_ENV !== 'production') {
  global.prisma = prisma;
}

// Test connection
prisma.$connect()
  .then(() => {
    logger.info('✅ Database connected');
  })
  .catch((error) => {
    logger.error('❌ Database connection failed:', error);
    process.exit(1);
  });

export default prisma;
