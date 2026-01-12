/**
 * Reports Routes
 */

import { Router } from 'express';
import { body } from 'express-validator';
import { validate } from '../middleware/validate';
import { authenticate } from '../middleware/auth';
import { asyncHandler } from '../middleware/error';
import * as reportController from '../controllers/reports';

const router = Router();

// Create report
router.post(
  '/',
  authenticate,
  [
    body('type').isIn(['user', 'post', 'comment', 'message']),
    body('target_id').isInt(),
    body('reason').isIn(['spam', 'harassment', 'hate_speech', 'misinformation', 'inappropriate', 'violence', 'self_harm', 'other']),
    body('details').optional().trim().isLength({ max: 1000 }),
  ],
  validate,
  asyncHandler(reportController.createReport)
);

export default router;
