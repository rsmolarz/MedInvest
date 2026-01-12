/**
 * Authentication Routes
 */

import { Router } from 'express';
import { body } from 'express-validator';
import { validate } from '../middleware/validate';
import { authenticate } from '../middleware/auth';
import { asyncHandler } from '../middleware/error';
import * as authController from '../controllers/auth';

const router = Router();

// Register
router.post(
  '/register',
  [
    body('email').isEmail().normalizeEmail().withMessage('Valid email is required'),
    body('password')
      .isLength({ min: 8 })
      .withMessage('Password must be at least 8 characters')
      .matches(/[A-Z]/)
      .withMessage('Password must contain uppercase letter')
      .matches(/[0-9]/)
      .withMessage('Password must contain a number'),
    body('full_name')
      .trim()
      .isLength({ min: 2, max: 100 })
      .withMessage('Name must be 2-100 characters'),
    body('specialty').optional().trim(),
  ],
  validate,
  asyncHandler(authController.register)
);

// Login
router.post(
  '/login',
  [
    body('email').isEmail().normalizeEmail().withMessage('Valid email is required'),
    body('password').notEmpty().withMessage('Password is required'),
  ],
  validate,
  asyncHandler(authController.login)
);

// Logout
router.post('/logout', authenticate, asyncHandler(authController.logout));

// Refresh token
router.post(
  '/refresh',
  [body('refresh_token').notEmpty().withMessage('Refresh token is required')],
  validate,
  asyncHandler(authController.refreshToken)
);

// Forgot password
router.post(
  '/forgot-password',
  [body('email').isEmail().normalizeEmail().withMessage('Valid email is required')],
  validate,
  asyncHandler(authController.forgotPassword)
);

// Reset password
router.post(
  '/reset-password',
  [
    body('token').notEmpty().withMessage('Token is required'),
    body('password')
      .isLength({ min: 8 })
      .withMessage('Password must be at least 8 characters'),
  ],
  validate,
  asyncHandler(authController.resetPassword)
);

// Verify email
router.post(
  '/verify-email',
  [body('token').notEmpty().withMessage('Token is required')],
  validate,
  asyncHandler(authController.verifyEmail)
);

// Resend verification email
router.post(
  '/resend-verification',
  [body('email').isEmail().normalizeEmail().withMessage('Valid email is required')],
  validate,
  asyncHandler(authController.resendVerification)
);

// Get current user
router.get('/me', authenticate, asyncHandler(authController.getCurrentUser));

export default router;
