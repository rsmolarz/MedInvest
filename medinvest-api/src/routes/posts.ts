/**
 * Post Routes
 */

import { Router } from 'express';
import { body, param, query } from 'express-validator';
import { validate } from '../middleware/validate';
import { authenticate, optionalAuth } from '../middleware/auth';
import { asyncHandler } from '../middleware/error';
import * as postController from '../controllers/posts';

const router = Router();

// Get feed
router.get(
  '/feed',
  optionalAuth,
  [
    query('page').optional().isInt({ min: 1 }),
    query('limit').optional().isInt({ min: 1, max: 100 }),
    query('room_id').optional().isInt(),
  ],
  validate,
  asyncHandler(postController.getFeed)
);

// Get bookmarks
router.get(
  '/bookmarks',
  authenticate,
  [
    query('page').optional().isInt({ min: 1 }),
    query('limit').optional().isInt({ min: 1, max: 100 }),
  ],
  validate,
  asyncHandler(postController.getBookmarks)
);

// Get post by ID
router.get(
  '/:id',
  optionalAuth,
  param('id').isInt(),
  validate,
  asyncHandler(postController.getPost)
);

// Create post
router.post(
  '/',
  authenticate,
  [
    body('content').trim().isLength({ min: 1, max: 5000 }),
    body('room_id').optional().isInt(),
    body('is_anonymous').optional().isBoolean(),
    body('images').optional().isArray({ max: 10 }),
    body('images.*').optional().isURL(),
    body('video_url').optional().isURL(),
    body('poll').optional().isObject(),
    body('poll.question').optional().trim().isLength({ min: 1, max: 150 }),
    body('poll.options').optional().isArray({ min: 2, max: 6 }),
    body('poll.duration').optional().isIn(['1day', '3days', '7days', 'none']),
    body('poll.allow_multiple').optional().isBoolean(),
    body('poll.is_anonymous').optional().isBoolean(),
  ],
  validate,
  asyncHandler(postController.createPost)
);

// Update post
router.put(
  '/:id',
  authenticate,
  [
    param('id').isInt(),
    body('content').optional().trim().isLength({ min: 1, max: 5000 }),
  ],
  validate,
  asyncHandler(postController.updatePost)
);

// Delete post
router.delete(
  '/:id',
  authenticate,
  param('id').isInt(),
  validate,
  asyncHandler(postController.deletePost)
);

// Like post
router.post(
  '/:id/like',
  authenticate,
  param('id').isInt(),
  validate,
  asyncHandler(postController.likePost)
);

// Unlike post
router.delete(
  '/:id/like',
  authenticate,
  param('id').isInt(),
  validate,
  asyncHandler(postController.unlikePost)
);

// React to post
router.post(
  '/:id/react',
  authenticate,
  [
    param('id').isInt(),
    body('type').isIn(['like', 'love', 'laugh', 'wow', 'sad', 'fire', 'thinking', 'clap']),
  ],
  validate,
  asyncHandler(postController.reactToPost)
);

// Remove reaction
router.delete(
  '/:id/react',
  authenticate,
  param('id').isInt(),
  validate,
  asyncHandler(postController.removeReaction)
);

// Bookmark post
router.post(
  '/:id/bookmark',
  authenticate,
  param('id').isInt(),
  validate,
  asyncHandler(postController.bookmarkPost)
);

// Remove bookmark
router.delete(
  '/:id/bookmark',
  authenticate,
  param('id').isInt(),
  validate,
  asyncHandler(postController.removeBookmark)
);

// Pin post
router.post(
  '/:id/pin',
  authenticate,
  param('id').isInt(),
  validate,
  asyncHandler(postController.pinPost)
);

// Unpin post
router.delete(
  '/:id/pin',
  authenticate,
  param('id').isInt(),
  validate,
  asyncHandler(postController.unpinPost)
);

// Report post
router.post(
  '/:id/report',
  authenticate,
  [
    param('id').isInt(),
    body('reason').isIn(['spam', 'harassment', 'hate_speech', 'misinformation', 'inappropriate', 'violence', 'self_harm', 'other']),
    body('details').optional().trim().isLength({ max: 1000 }),
  ],
  validate,
  asyncHandler(postController.reportPost)
);

// Get comments for a post
router.get(
  '/:id/comments',
  optionalAuth,
  [
    param('id').isInt(),
    query('page').optional().isInt({ min: 1 }),
    query('limit').optional().isInt({ min: 1, max: 100 }),
  ],
  validate,
  asyncHandler(postController.getComments)
);

// Create comment on post
router.post(
  '/:id/comments',
  authenticate,
  [
    param('id').isInt(),
    body('content').trim().isLength({ min: 1, max: 2000 }),
    body('parent_id').optional().isInt(),
  ],
  validate,
  asyncHandler(postController.createComment)
);

// Vote on poll
router.post(
  '/:postId/polls/:pollId/vote',
  authenticate,
  [
    param('postId').isInt(),
    param('pollId').isUUID(),
    body('option_ids').isArray({ min: 1 }),
    body('option_ids.*').isUUID(),
  ],
  validate,
  asyncHandler(postController.votePoll)
);

export default router;
