/**
 * Request Logger Middleware
 */

import { Request, Response, NextFunction } from 'express';
import { logger } from '../utils/logger';

export function requestLogger(req: Request, res: Response, next: NextFunction) {
  const start = Date.now();
  
  // Log request
  res.on('finish', () => {
    const duration = Date.now() - start;
    const logLevel = res.statusCode >= 400 ? 'warn' : 'info';
    
    logger[logLevel](
      `${req.method} ${req.path} ${res.statusCode} - ${duration}ms`,
      {
        method: req.method,
        path: req.path,
        statusCode: res.statusCode,
        duration,
        userAgent: req.get('user-agent'),
        ip: req.ip,
        userId: req.user?.id,
      }
    );
  });
  
  next();
}
