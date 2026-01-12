/**
 * Conversations Routes
 */

import { Router } from 'express';
import { body, param, query } from 'express-validator';
import { validate } from '../middleware/validate';
import { authenticate } from '../middleware/auth';
import { asyncHandler } from '../middleware/error';
import * as conversationController from '../controllers/conversations';

const router = Router();

// Get all conversations
router.get(
  '/',
  authenticate,
  [
    query('page').optional().isInt({ min: 1 }),
    query('limit').optional().isInt({ min: 1, max: 100 }),
  ],
  validate,
  asyncHandler(conversationController.getConversations)
);

// Create conversation
router.post(
  '/',
  authenticate,
  body('user_id').isInt(),
  validate,
  asyncHandler(conversationController.createConversation)
);

// Get conversation
router.get(
  '/:id',
  authenticate,
  param('id').isInt(),
  validate,
  asyncHandler(conversationController.getConversation)
);

// Delete conversation
router.delete(
  '/:id',
  authenticate,
  param('id').isInt(),
  validate,
  asyncHandler(conversationController.deleteConversation)
);

// Get messages
router.get(
  '/:id/messages',
  authenticate,
  [
    param('id').isInt(),
    query('page').optional().isInt({ min: 1 }),
    query('limit').optional().isInt({ min: 1, max: 100 }),
  ],
  validate,
  asyncHandler(conversationController.getMessages)
);

// Send message
router.post(
  '/:id/messages',
  authenticate,
  [
    param('id').isInt(),
    body('content').trim().isLength({ min: 1, max: 5000 }),
    body('attachments').optional().isArray({ max: 5 }),
  ],
  validate,
  asyncHandler(conversationController.sendMessage)
);

// Mark as read
router.post(
  '/:id/read',
  authenticate,
  param('id').isInt(),
  validate,
  asyncHandler(conversationController.markAsRead)
);

// Mute conversation
router.post(
  '/:id/mute',
  authenticate,
  param('id').isInt(),
  validate,
  asyncHandler(conversationController.muteConversation)
);

// Unmute conversation
router.delete(
  '/:id/mute',
  authenticate,
  param('id').isInt(),
  validate,
  asyncHandler(conversationController.unmuteConversation)
);

export default router;
