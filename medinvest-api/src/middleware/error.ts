/**
 * Error Handling Middleware
 */

import { Request, Response, NextFunction } from 'express';
import { logger } from '../utils/logger';

/**
 * Custom API Error
 */
export class ApiError extends Error {
  statusCode: number;
  code: string;
  details?: Record<string, string[]>;
  
  constructor(
    statusCode: number, 
    code: string, 
    message: string, 
    details?: Record<string, string[]>
  ) {
    super(message);
    this.statusCode = statusCode;
    this.code = code;
    this.details = details;
    
    Error.captureStackTrace(this, this.constructor);
  }
  
  // Common error factory methods
  static badRequest(message: string, details?: Record<string, string[]>) {
    return new ApiError(400, 'BAD_REQUEST', message, details);
  }
  
  static unauthorized(message = 'Unauthorized') {
    return new ApiError(401, 'UNAUTHORIZED', message);
  }
  
  static forbidden(message = 'Forbidden') {
    return new ApiError(403, 'FORBIDDEN', message);
  }
  
  static notFound(message = 'Resource not found') {
    return new ApiError(404, 'NOT_FOUND', message);
  }
  
  static conflict(message: string) {
    return new ApiError(409, 'CONFLICT', message);
  }
  
  static validationError(details: Record<string, string[]>) {
    return new ApiError(422, 'VALIDATION_ERROR', 'Validation failed', details);
  }
  
  static tooManyRequests(message = 'Too many requests') {
    return new ApiError(429, 'RATE_LIMIT', message);
  }
  
  static internal(message = 'Internal server error') {
    return new ApiError(500, 'SERVER_ERROR', message);
  }
}

/**
 * Not found handler (404)
 */
export function notFoundHandler(req: Request, res: Response, next: NextFunction) {
  res.status(404).json({
    success: false,
    error: {
      code: 'NOT_FOUND',
      message: `Route ${req.method} ${req.path} not found`,
    },
  });
}

/**
 * Global error handler
 */
export function errorHandler(
  error: Error | ApiError, 
  req: Request, 
  res: Response, 
  next: NextFunction
) {
  // Log error
  logger.error('Error:', {
    message: error.message,
    stack: error.stack,
    path: req.path,
    method: req.method,
  });
  
  // Handle ApiError
  if (error instanceof ApiError) {
    return res.status(error.statusCode).json({
      success: false,
      error: {
        code: error.code,
        message: error.message,
        ...(error.details && { details: error.details }),
      },
    });
  }
  
  // Handle Prisma errors
  if (error.name === 'PrismaClientKnownRequestError') {
    const prismaError = error as any;
    
    switch (prismaError.code) {
      case 'P2002':
        // Unique constraint violation
        return res.status(409).json({
          success: false,
          error: {
            code: 'CONFLICT',
            message: 'A record with this value already exists',
          },
        });
      case 'P2025':
        // Record not found
        return res.status(404).json({
          success: false,
          error: {
            code: 'NOT_FOUND',
            message: 'Record not found',
          },
        });
      default:
        break;
    }
  }
  
  // Handle validation errors from express-validator
  if (error.name === 'ValidationError') {
    return res.status(422).json({
      success: false,
      error: {
        code: 'VALIDATION_ERROR',
        message: error.message,
      },
    });
  }
  
  // Handle JWT errors
  if (error.name === 'JsonWebTokenError') {
    return res.status(401).json({
      success: false,
      error: {
        code: 'INVALID_TOKEN',
        message: 'Invalid token',
      },
    });
  }
  
  if (error.name === 'TokenExpiredError') {
    return res.status(401).json({
      success: false,
      error: {
        code: 'TOKEN_EXPIRED',
        message: 'Token has expired',
      },
    });
  }
  
  // Default error response
  const statusCode = 500;
  const message = process.env.NODE_ENV === 'production' 
    ? 'Internal server error' 
    : error.message;
  
  res.status(statusCode).json({
    success: false,
    error: {
      code: 'SERVER_ERROR',
      message,
      ...(process.env.NODE_ENV !== 'production' && { stack: error.stack }),
    },
  });
}

/**
 * Async handler wrapper
 * Catches errors in async route handlers
 */
export function asyncHandler(fn: (req: Request, res: Response, next: NextFunction) => Promise<any>) {
  return (req: Request, res: Response, next: NextFunction) => {
    Promise.resolve(fn(req, res, next)).catch(next);
  };
}
