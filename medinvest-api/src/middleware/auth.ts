/**
 * Authentication Middleware
 */

import { Request, Response, NextFunction } from 'express';
import { verifyToken, TokenPayload } from '../utils/jwt';
import prisma from '../config/database';
import { logger } from '../utils/logger';

// Extend Express Request type
declare global {
  namespace Express {
    interface Request {
      user?: {
        id: number;
        email: string;
        is_admin: boolean;
        is_premium: boolean;
      };
    }
  }
}

/**
 * Require authentication
 */
export async function authenticate(req: Request, res: Response, next: NextFunction) {
  try {
    const authHeader = req.headers.authorization;
    
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return res.status(401).json({
        success: false,
        error: {
          code: 'UNAUTHORIZED',
          message: 'No token provided',
        },
      });
    }
    
    const token = authHeader.split(' ')[1];
    
    let payload: TokenPayload;
    try {
      payload = verifyToken(token);
    } catch (error) {
      return res.status(401).json({
        success: false,
        error: {
          code: 'TOKEN_EXPIRED',
          message: 'Token is invalid or expired',
        },
      });
    }
    
    // Check token type
    if (payload.type !== 'access') {
      return res.status(401).json({
        success: false,
        error: {
          code: 'INVALID_TOKEN',
          message: 'Invalid token type',
        },
      });
    }
    
    // Get user from database
    const user = await prisma.user.findUnique({
      where: { id: payload.userId },
      select: {
        id: true,
        email: true,
        is_admin: true,
        is_premium: true,
        email_verified: true,
      },
    });
    
    if (!user) {
      return res.status(401).json({
        success: false,
        error: {
          code: 'USER_NOT_FOUND',
          message: 'User not found',
        },
      });
    }
    
    // Attach user to request
    req.user = {
      id: user.id,
      email: user.email,
      is_admin: user.is_admin,
      is_premium: user.is_premium,
    };
    
    next();
  } catch (error) {
    logger.error('Auth middleware error:', error);
    return res.status(500).json({
      success: false,
      error: {
        code: 'SERVER_ERROR',
        message: 'Authentication failed',
      },
    });
  }
}

/**
 * Optional authentication (attach user if token provided)
 */
export async function optionalAuth(req: Request, res: Response, next: NextFunction) {
  const authHeader = req.headers.authorization;
  
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return next();
  }
  
  try {
    const token = authHeader.split(' ')[1];
    const payload = verifyToken(token);
    
    if (payload.type === 'access') {
      const user = await prisma.user.findUnique({
        where: { id: payload.userId },
        select: {
          id: true,
          email: true,
          is_admin: true,
          is_premium: true,
        },
      });
      
      if (user) {
        req.user = {
          id: user.id,
          email: user.email,
          is_admin: user.is_admin,
          is_premium: user.is_premium,
        };
      }
    }
  } catch (error) {
    // Token invalid, continue without user
  }
  
  next();
}

/**
 * Require admin role
 */
export function requireAdmin(req: Request, res: Response, next: NextFunction) {
  if (!req.user?.is_admin) {
    return res.status(403).json({
      success: false,
      error: {
        code: 'FORBIDDEN',
        message: 'Admin access required',
      },
    });
  }
  
  next();
}

/**
 * Require premium subscription
 */
export function requirePremium(req: Request, res: Response, next: NextFunction) {
  if (!req.user?.is_premium && !req.user?.is_admin) {
    return res.status(403).json({
      success: false,
      error: {
        code: 'PREMIUM_REQUIRED',
        message: 'Premium subscription required',
      },
    });
  }
  
  next();
}

/**
 * Require email verification
 */
export async function requireVerifiedEmail(req: Request, res: Response, next: NextFunction) {
  if (!req.user) {
    return res.status(401).json({
      success: false,
      error: {
        code: 'UNAUTHORIZED',
        message: 'Authentication required',
      },
    });
  }
  
  const user = await prisma.user.findUnique({
    where: { id: req.user.id },
    select: { email_verified: true },
  });
  
  if (!user?.email_verified) {
    return res.status(403).json({
      success: false,
      error: {
        code: 'EMAIL_NOT_VERIFIED',
        message: 'Please verify your email address',
      },
    });
  }
  
  next();
}
