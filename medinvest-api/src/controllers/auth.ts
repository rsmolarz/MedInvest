/**
 * Authentication Controller
 */

import { Request, Response } from 'express';
import { nanoid } from 'nanoid';
import prisma from '../config/database';
import { hashPassword, comparePassword } from '../utils/password';
import { generateTokenPair, verifyToken } from '../utils/jwt';
import { ApiError } from '../middleware/error';
import { sendVerificationEmail, sendPasswordResetEmail } from '../services/email';
import { logger } from '../utils/logger';

/**
 * Register new user
 */
export async function register(req: Request, res: Response) {
  const { email, password, full_name, specialty } = req.body;
  
  // Check if email already exists
  const existingUser = await prisma.user.findUnique({
    where: { email: email.toLowerCase() },
  });
  
  if (existingUser) {
    throw ApiError.conflict('Email already registered');
  }
  
  // Hash password
  const hashedPassword = await hashPassword(password);
  
  // Create user
  const user = await prisma.user.create({
    data: {
      email: email.toLowerCase(),
      password: hashedPassword,
      full_name,
      specialty,
    },
    select: {
      id: true,
      email: true,
      full_name: true,
      specialty: true,
      created_at: true,
    },
  });
  
  // Create verification token
  const verificationToken = nanoid(32);
  const expiresAt = new Date(Date.now() + 24 * 60 * 60 * 1000); // 24 hours
  
  await prisma.verificationToken.create({
    data: {
      token: verificationToken,
      type: 'email_verify',
      user_id: user.id,
      expires_at: expiresAt,
    },
  });
  
  // Send verification email
  try {
    await sendVerificationEmail(user.email, user.full_name, verificationToken);
  } catch (error) {
    logger.error('Failed to send verification email:', error);
  }
  
  // Create default settings
  await prisma.userSettings.create({
    data: { user_id: user.id },
  });
  
  res.status(201).json({
    success: true,
    data: {
      user,
      message: 'Registration successful. Please check your email to verify your account.',
    },
  });
}

/**
 * Login
 */
export async function login(req: Request, res: Response) {
  const { email, password } = req.body;
  
  // Find user
  const user = await prisma.user.findUnique({
    where: { email: email.toLowerCase() },
  });
  
  if (!user) {
    throw ApiError.unauthorized('Invalid email or password');
  }
  
  // Verify password
  const isValidPassword = await comparePassword(password, user.password);
  
  if (!isValidPassword) {
    throw ApiError.unauthorized('Invalid email or password');
  }
  
  // Generate tokens
  const { accessToken, refreshToken } = generateTokenPair(user.id, user.email);
  
  // Store refresh token
  const expiresAt = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000); // 30 days
  await prisma.refreshToken.create({
    data: {
      token: refreshToken,
      user_id: user.id,
      expires_at: expiresAt,
    },
  });
  
  // Update last seen
  await prisma.user.update({
    where: { id: user.id },
    data: { last_seen_at: new Date() },
  });
  
  res.json({
    success: true,
    data: {
      token: accessToken,
      refresh_token: refreshToken,
      user: {
        id: user.id,
        email: user.email,
        full_name: user.full_name,
        username: user.username,
        avatar_url: user.avatar_url,
        bio: user.bio,
        specialty: user.specialty,
        is_verified: user.is_verified,
        is_premium: user.is_premium,
        email_verified: user.email_verified,
      },
    },
  });
}

/**
 * Logout
 */
export async function logout(req: Request, res: Response) {
  // Optionally invalidate refresh tokens
  // For now, just return success
  res.json({
    success: true,
    message: 'Logged out successfully',
  });
}

/**
 * Refresh access token
 */
export async function refreshToken(req: Request, res: Response) {
  const { refresh_token } = req.body;
  
  // Verify token
  let payload;
  try {
    payload = verifyToken(refresh_token);
  } catch (error) {
    throw ApiError.unauthorized('Invalid or expired refresh token');
  }
  
  if (payload.type !== 'refresh') {
    throw ApiError.unauthorized('Invalid token type');
  }
  
  // Check if token exists in database
  const storedToken = await prisma.refreshToken.findUnique({
    where: { token: refresh_token },
    include: { user: true },
  });
  
  if (!storedToken || storedToken.expires_at < new Date()) {
    throw ApiError.unauthorized('Invalid or expired refresh token');
  }
  
  // Generate new tokens
  const { accessToken, refreshToken: newRefreshToken } = generateTokenPair(
    storedToken.user.id,
    storedToken.user.email
  );
  
  // Delete old refresh token and create new one
  await prisma.refreshToken.delete({ where: { id: storedToken.id } });
  
  const expiresAt = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000);
  await prisma.refreshToken.create({
    data: {
      token: newRefreshToken,
      user_id: storedToken.user.id,
      expires_at: expiresAt,
    },
  });
  
  res.json({
    success: true,
    data: {
      token: accessToken,
      refresh_token: newRefreshToken,
    },
  });
}

/**
 * Request password reset
 */
export async function forgotPassword(req: Request, res: Response) {
  const { email } = req.body;
  
  // Find user (don't reveal if email exists)
  const user = await prisma.user.findUnique({
    where: { email: email.toLowerCase() },
  });
  
  if (user) {
    // Create reset token
    const resetToken = nanoid(32);
    const expiresAt = new Date(Date.now() + 60 * 60 * 1000); // 1 hour
    
    await prisma.verificationToken.create({
      data: {
        token: resetToken,
        type: 'password_reset',
        user_id: user.id,
        expires_at: expiresAt,
      },
    });
    
    // Send email
    try {
      await sendPasswordResetEmail(user.email, user.full_name, resetToken);
    } catch (error) {
      logger.error('Failed to send password reset email:', error);
    }
  }
  
  // Always return success to prevent email enumeration
  res.json({
    success: true,
    message: 'If an account exists with this email, you will receive a password reset link.',
  });
}

/**
 * Reset password
 */
export async function resetPassword(req: Request, res: Response) {
  const { token, password } = req.body;
  
  // Find valid token
  const verificationToken = await prisma.verificationToken.findFirst({
    where: {
      token,
      type: 'password_reset',
      expires_at: { gt: new Date() },
      used_at: null,
    },
    include: { user: true },
  });
  
  if (!verificationToken) {
    throw ApiError.badRequest('Invalid or expired reset token');
  }
  
  // Hash new password
  const hashedPassword = await hashPassword(password);
  
  // Update password and mark token as used
  await prisma.$transaction([
    prisma.user.update({
      where: { id: verificationToken.user_id },
      data: { password: hashedPassword },
    }),
    prisma.verificationToken.update({
      where: { id: verificationToken.id },
      data: { used_at: new Date() },
    }),
    // Invalidate all refresh tokens
    prisma.refreshToken.deleteMany({
      where: { user_id: verificationToken.user_id },
    }),
  ]);
  
  res.json({
    success: true,
    message: 'Password reset successfully. Please login with your new password.',
  });
}

/**
 * Verify email
 */
export async function verifyEmail(req: Request, res: Response) {
  const { token } = req.body;
  
  // Find valid token
  const verificationToken = await prisma.verificationToken.findFirst({
    where: {
      token,
      type: 'email_verify',
      expires_at: { gt: new Date() },
      used_at: null,
    },
  });
  
  if (!verificationToken) {
    throw ApiError.badRequest('Invalid or expired verification token');
  }
  
  // Update user and mark token as used
  await prisma.$transaction([
    prisma.user.update({
      where: { id: verificationToken.user_id },
      data: {
        email_verified: true,
        email_verified_at: new Date(),
      },
    }),
    prisma.verificationToken.update({
      where: { id: verificationToken.id },
      data: { used_at: new Date() },
    }),
  ]);
  
  res.json({
    success: true,
    message: 'Email verified successfully.',
  });
}

/**
 * Resend verification email
 */
export async function resendVerification(req: Request, res: Response) {
  const { email } = req.body;
  
  const user = await prisma.user.findUnique({
    where: { email: email.toLowerCase() },
  });
  
  if (user && !user.email_verified) {
    // Delete existing tokens
    await prisma.verificationToken.deleteMany({
      where: {
        user_id: user.id,
        type: 'email_verify',
      },
    });
    
    // Create new token
    const verificationToken = nanoid(32);
    const expiresAt = new Date(Date.now() + 24 * 60 * 60 * 1000);
    
    await prisma.verificationToken.create({
      data: {
        token: verificationToken,
        type: 'email_verify',
        user_id: user.id,
        expires_at: expiresAt,
      },
    });
    
    // Send email
    try {
      await sendVerificationEmail(user.email, user.full_name, verificationToken);
    } catch (error) {
      logger.error('Failed to send verification email:', error);
    }
  }
  
  res.json({
    success: true,
    message: 'If an unverified account exists with this email, a verification link has been sent.',
  });
}

/**
 * Get current user
 */
export async function getCurrentUser(req: Request, res: Response) {
  const user = await prisma.user.findUnique({
    where: { id: req.user!.id },
    select: {
      id: true,
      email: true,
      full_name: true,
      username: true,
      avatar_url: true,
      bio: true,
      specialty: true,
      credentials: true,
      location: true,
      website: true,
      is_verified: true,
      is_premium: true,
      is_admin: true,
      email_verified: true,
      followers_count: true,
      following_count: true,
      posts_count: true,
      created_at: true,
    },
  });
  
  if (!user) {
    throw ApiError.notFound('User not found');
  }
  
  // Get counts
  const [followersCount, followingCount, postsCount] = await Promise.all([
    prisma.follow.count({ where: { following_id: user.id } }),
    prisma.follow.count({ where: { follower_id: user.id } }),
    prisma.post.count({ where: { author_id: user.id, deleted_at: null } }),
  ]);
  
  res.json({
    success: true,
    data: {
      ...user,
      followers_count: followersCount,
      following_count: followingCount,
      posts_count: postsCount,
    },
  });
}
