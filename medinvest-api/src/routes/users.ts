/**
 * User Routes
 */

import { Router } from 'express';
import { body, param, query } from 'express-validator';
import { validate } from '../middleware/validate';
import { authenticate, optionalAuth } from '../middleware/auth';
import { asyncHandler } from '../middleware/error';
import * as userController from '../controllers/users';

const router = Router();

// Get current user profile
router.get('/me', authenticate, asyncHandler(userController.getCurrentUser));

// Update current user profile
router.put(
  '/me',
  authenticate,
  [
    body('full_name').optional().trim().isLength({ min: 2, max: 100 }),
    body('username').optional().trim().isLength({ min: 3, max: 30 }).matches(/^[a-zA-Z0-9_]+$/),
    body('bio').optional().trim().isLength({ max: 500 }),
    body('specialty').optional().trim(),
    body('credentials').optional().trim().isLength({ max: 200 }),
    body('location').optional().trim().isLength({ max: 100 }),
    body('website').optional().trim().isURL().or(body('website').isEmpty()),
  ],
  validate,
  asyncHandler(userController.updateProfile)
);

// Change password
router.put(
  '/me/password',
  authenticate,
  [
    body('current_password').notEmpty(),
    body('new_password').isLength({ min: 8 }),
  ],
  validate,
  asyncHandler(userController.changePassword)
);

// Get user by ID
router.get(
  '/:id',
  optionalAuth,
  param('id').isInt(),
  validate,
  asyncHandler(userController.getUserById)
);

// Get user by username
router.get(
  '/username/:username',
  optionalAuth,
  param('username').isLength({ min: 3 }),
  validate,
  asyncHandler(userController.getUserByUsername)
);

// Get user's posts
router.get(
  '/:id/posts',
  optionalAuth,
  [
    param('id').isInt(),
    query('page').optional().isInt({ min: 1 }),
    query('limit').optional().isInt({ min: 1, max: 100 }),
  ],
  validate,
  asyncHandler(userController.getUserPosts)
);

// Get user's pinned posts
router.get(
  '/:id/pinned-posts',
  optionalAuth,
  param('id').isInt(),
  validate,
  asyncHandler(userController.getPinnedPosts)
);

// Follow user
router.post(
  '/:id/follow',
  authenticate,
  param('id').isInt(),
  validate,
  asyncHandler(userController.followUser)
);

// Unfollow user
router.delete(
  '/:id/follow',
  authenticate,
  param('id').isInt(),
  validate,
  asyncHandler(userController.unfollowUser)
);

// Get followers
router.get(
  '/:id/followers',
  optionalAuth,
  [
    param('id').isInt(),
    query('page').optional().isInt({ min: 1 }),
    query('limit').optional().isInt({ min: 1, max: 100 }),
  ],
  validate,
  asyncHandler(userController.getFollowers)
);

// Get following
router.get(
  '/:id/following',
  optionalAuth,
  [
    param('id').isInt(),
    query('page').optional().isInt({ min: 1 }),
    query('limit').optional().isInt({ min: 1, max: 100 }),
  ],
  validate,
  asyncHandler(userController.getFollowing)
);

// Block user
router.post(
  '/:id/block',
  authenticate,
  param('id').isInt(),
  validate,
  asyncHandler(userController.blockUser)
);

// Unblock user
router.delete(
  '/:id/block',
  authenticate,
  param('id').isInt(),
  validate,
  asyncHandler(userController.unblockUser)
);

// Get blocked users
router.get('/blocked', authenticate, asyncHandler(userController.getBlockedUsers));

// Mute user
router.post(
  '/:id/mute',
  authenticate,
  [
    param('id').isInt(),
    body('mute_posts').optional().isBoolean(),
    body('mute_comments').optional().isBoolean(),
    body('mute_messages').optional().isBoolean(),
    body('duration').isIn(['1hour', '8hours', '24hours', '7days', '30days', 'forever']),
  ],
  validate,
  asyncHandler(userController.muteUser)
);

// Unmute user
router.delete(
  '/:id/mute',
  authenticate,
  param('id').isInt(),
  validate,
  asyncHandler(userController.unmuteUser)
);

// Get muted users
router.get('/muted', authenticate, asyncHandler(userController.getMutedUsers));

export default router;
