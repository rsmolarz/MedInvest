/**
 * Notifications Routes
 */

import { Router } from 'express';
import { param, query } from 'express-validator';
import { validate } from '../middleware/validate';
import { authenticate } from '../middleware/auth';
import { asyncHandler } from '../middleware/error';
import * as notificationController from '../controllers/notifications';

const router = Router();

// Get notifications
router.get(
  '/',
  authenticate,
  [
    query('page').optional().isInt({ min: 1 }),
    query('limit').optional().isInt({ min: 1, max: 100 }),
  ],
  validate,
  asyncHandler(notificationController.getNotifications)
);

// Get unread count
router.get('/unread-count', authenticate, asyncHandler(notificationController.getUnreadCount));

// Mark notification as read
router.post(
  '/:id/read',
  authenticate,
  param('id').isInt(),
  validate,
  asyncHandler(notificationController.markAsRead)
);

// Mark all as read
router.post('/read-all', authenticate, asyncHandler(notificationController.markAllAsRead));

export default router;
