/**
 * Rooms Routes
 */

import { Router } from 'express';
import { param, query } from 'express-validator';
import { validate } from '../middleware/validate';
import { authenticate, optionalAuth } from '../middleware/auth';
import { asyncHandler } from '../middleware/error';
import * as roomController from '../controllers/rooms';

const router = Router();

// Get all rooms
router.get('/', optionalAuth, asyncHandler(roomController.getRooms));

// Get joined rooms
router.get('/joined', authenticate, asyncHandler(roomController.getJoinedRooms));

// Get room by ID
router.get(
  '/:id',
  optionalAuth,
  param('id').isInt(),
  validate,
  asyncHandler(roomController.getRoom)
);

// Get room posts
router.get(
  '/:id/posts',
  optionalAuth,
  [
    param('id').isInt(),
    query('page').optional().isInt({ min: 1 }),
    query('limit').optional().isInt({ min: 1, max: 100 }),
  ],
  validate,
  asyncHandler(roomController.getRoomPosts)
);

// Join room
router.post(
  '/:id/join',
  authenticate,
  param('id').isInt(),
  validate,
  asyncHandler(roomController.joinRoom)
);

// Leave room
router.delete(
  '/:id/join',
  authenticate,
  param('id').isInt(),
  validate,
  asyncHandler(roomController.leaveRoom)
);

export default router;
