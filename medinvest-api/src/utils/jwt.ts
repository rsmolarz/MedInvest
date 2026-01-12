/**
 * JWT Utilities
 */

import jwt from 'jsonwebtoken';
import { config } from '../config';

export interface TokenPayload {
  userId: number;
  email: string;
  type: 'access' | 'refresh';
}

/**
 * Generate access token
 */
export function generateAccessToken(userId: number, email: string): string {
  const payload: TokenPayload = {
    userId,
    email,
    type: 'access',
  };
  
  return jwt.sign(payload, config.jwtSecret, {
    expiresIn: config.jwtExpiresIn,
  });
}

/**
 * Generate refresh token
 */
export function generateRefreshToken(userId: number, email: string): string {
  const payload: TokenPayload = {
    userId,
    email,
    type: 'refresh',
  };
  
  return jwt.sign(payload, config.jwtSecret, {
    expiresIn: config.refreshTokenExpiresIn,
  });
}

/**
 * Verify token
 */
export function verifyToken(token: string): TokenPayload {
  return jwt.verify(token, config.jwtSecret) as TokenPayload;
}

/**
 * Decode token without verification
 */
export function decodeToken(token: string): TokenPayload | null {
  try {
    return jwt.decode(token) as TokenPayload;
  } catch {
    return null;
  }
}

/**
 * Generate token pair
 */
export function generateTokenPair(userId: number, email: string) {
  return {
    accessToken: generateAccessToken(userId, email),
    refreshToken: generateRefreshToken(userId, email),
  };
}
