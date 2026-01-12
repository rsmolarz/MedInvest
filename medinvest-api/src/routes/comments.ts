/**
 * Comments Routes
 */

import { Router } from 'express';
import { body, param } from 'express-validator';
import { validate } from '../middleware/validate';
import { authenticate } from '../middleware/auth';
import { asyncHandler } from '../middleware/error';
import * as commentController from '../controllers/comments';

const router = Router();

// Update comment
router.put(
  '/:id',
  authenticate,
  [
    param('id').isInt(),
    body('content').trim().isLength({ min: 1, max: 2000 }),
  ],
  validate,
  asyncHandler(commentController.updateComment)
);

// Delete comment
router.delete(
  '/:id',
  authenticate,
  param('id').isInt(),
  validate,
  asyncHandler(commentController.deleteComment)
);

// Like comment
router.post(
  '/:id/like',
  authenticate,
  param('id').isInt(),
  validate,
  asyncHandler(commentController.likeComment)
);

// Unlike comment
router.delete(
  '/:id/like',
  authenticate,
  param('id').isInt(),
  validate,
  asyncHandler(commentController.unlikeComment)
);

export default router;
