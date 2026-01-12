/**
 * Application Configuration
 */

import dotenv from 'dotenv';

dotenv.config();

export const config = {
  // Server
  nodeEnv: process.env.NODE_ENV || 'development',
  port: parseInt(process.env.PORT || '3000', 10),
  
  // Database
  databaseUrl: process.env.DATABASE_URL || 'postgresql://localhost:5432/medinvest',
  
  // Redis (for caching, sessions, rate limiting)
  redisUrl: process.env.REDIS_URL || 'redis://localhost:6379',
  
  // JWT
  jwtSecret: process.env.JWT_SECRET || 'your-super-secret-jwt-key-change-in-production',
  jwtExpiresIn: process.env.JWT_EXPIRES_IN || '7d',
  refreshTokenExpiresIn: process.env.REFRESH_TOKEN_EXPIRES_IN || '30d',
  
  // CORS
  corsOrigins: (process.env.CORS_ORIGINS || 'http://localhost:3000,http://localhost:8081')
    .split(',')
    .map(origin => origin.trim()),
  
  // Email (Nodemailer)
  smtp: {
    host: process.env.SMTP_HOST || 'smtp.gmail.com',
    port: parseInt(process.env.SMTP_PORT || '587', 10),
    secure: process.env.SMTP_SECURE === 'true',
    user: process.env.SMTP_USER || '',
    pass: process.env.SMTP_PASS || '',
    from: process.env.SMTP_FROM || 'MedInvest <noreply@medinvest.com>',
  },
  
  // File uploads
  uploads: {
    maxFileSize: parseInt(process.env.MAX_FILE_SIZE || '10485760', 10), // 10MB
    allowedImageTypes: ['image/jpeg', 'image/png', 'image/gif', 'image/webp'],
    allowedVideoTypes: ['video/mp4', 'video/quicktime', 'video/webm'],
    storageProvider: process.env.STORAGE_PROVIDER || 'local', // local, s3, cloudinary
  },
  
  // AWS S3 (optional)
  aws: {
    accessKeyId: process.env.AWS_ACCESS_KEY_ID || '',
    secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY || '',
    region: process.env.AWS_REGION || 'us-east-1',
    bucket: process.env.AWS_S3_BUCKET || '',
  },
  
  // Stripe
  stripe: {
    secretKey: process.env.STRIPE_SECRET_KEY || '',
    webhookSecret: process.env.STRIPE_WEBHOOK_SECRET || '',
    priceIdMonthly: process.env.STRIPE_PRICE_ID_MONTHLY || '',
    priceIdYearly: process.env.STRIPE_PRICE_ID_YEARLY || '',
  },
  
  // Firebase (Push Notifications)
  firebase: {
    projectId: process.env.FIREBASE_PROJECT_ID || '',
    privateKey: process.env.FIREBASE_PRIVATE_KEY?.replace(/\\n/g, '\n') || '',
    clientEmail: process.env.FIREBASE_CLIENT_EMAIL || '',
  },
  
  // App URLs
  appUrl: process.env.APP_URL || 'http://localhost:3000',
  mobileScheme: process.env.MOBILE_SCHEME || 'medinvest',
  
  // Pagination defaults
  pagination: {
    defaultLimit: 20,
    maxLimit: 100,
  },
};

// Validate required config in production
if (config.nodeEnv === 'production') {
  const required = [
    'JWT_SECRET',
    'DATABASE_URL',
  ];
  
  for (const key of required) {
    if (!process.env[key]) {
      throw new Error(`Missing required environment variable: ${key}`);
    }
  }
}
