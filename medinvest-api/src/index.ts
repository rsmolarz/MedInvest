/**
 * MedInvest API Server
 * Main entry point
 */

import express from 'express';
import { createServer } from 'http';
import cors from 'cors';
import helmet from 'helmet';
import compression from 'compression';
import cookieParser from 'cookie-parser';
import rateLimit from 'express-rate-limit';
import { Server as SocketServer } from 'socket.io';

import { config } from './config';
import { logger } from './utils/logger';
import { errorHandler, notFoundHandler } from './middleware/error';
import { requestLogger } from './middleware/requestLogger';
import { setupWebSocket } from './websocket';
import routes from './routes';

// Initialize Express app
const app = express();
const httpServer = createServer(app);

// Initialize Socket.IO
const io = new SocketServer(httpServer, {
  cors: {
    origin: config.corsOrigins,
    methods: ['GET', 'POST'],
    credentials: true,
  },
});

// Make io available to routes
app.set('io', io);

// =============================================================================
// MIDDLEWARE
// =============================================================================

// Security headers
app.use(helmet());

// CORS
app.use(cors({
  origin: config.corsOrigins,
  credentials: true,
  methods: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization', 'X-Password'],
}));

// Compression
app.use(compression());

// Body parsing
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true, limit: '10mb' }));

// Cookie parsing
app.use(cookieParser());

// Request logging
app.use(requestLogger);

// Rate limiting
const limiter = rateLimit({
  windowMs: 60 * 1000, // 1 minute
  max: 100, // 100 requests per minute
  message: {
    success: false,
    error: {
      code: 'RATE_LIMIT',
      message: 'Too many requests, please try again later.',
    },
  },
  standardHeaders: true,
  legacyHeaders: false,
});
app.use('/api/', limiter);

// Auth rate limiting (stricter)
const authLimiter = rateLimit({
  windowMs: 60 * 1000,
  max: 10, // 10 auth attempts per minute
  message: {
    success: false,
    error: {
      code: 'RATE_LIMIT',
      message: 'Too many authentication attempts, please try again later.',
    },
  },
});
app.use('/api/v1/auth/', authLimiter);

// =============================================================================
// ROUTES
// =============================================================================

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// API routes
app.use('/api/v1', routes);

// =============================================================================
// ERROR HANDLING
// =============================================================================

app.use(notFoundHandler);
app.use(errorHandler);

// =============================================================================
// WEBSOCKET
// =============================================================================

setupWebSocket(io);

// =============================================================================
// START SERVER
// =============================================================================

const PORT = config.port;

httpServer.listen(PORT, () => {
  logger.info(`🚀 Server running on port ${PORT}`);
  logger.info(`📝 Environment: ${config.nodeEnv}`);
  logger.info(`🔗 API URL: http://localhost:${PORT}/api/v1`);
});

// Graceful shutdown
process.on('SIGTERM', () => {
  logger.info('SIGTERM received, shutting down gracefully');
  httpServer.close(() => {
    logger.info('Server closed');
    process.exit(0);
  });
});

export { app, httpServer, io };
