/**
 * Account Routes
 */

import { Router } from 'express';
import { body, param } from 'express-validator';
import { validate } from '../middleware/validate';
import { authenticate } from '../middleware/auth';
import { asyncHandler } from '../middleware/error';
import * as accountController from '../controllers/account';

const router = Router();

// Request data export
router.post(
  '/export',
  authenticate,
  [
    body('categories').isArray({ min: 1 }),
    body('categories.*').isIn(['profile', 'posts', 'comments', 'messages', 'likes', 'bookmarks', 'settings']),
    body('format').isIn(['json', 'csv', 'html']),
  ],
  validate,
  asyncHandler(accountController.requestExport)
);

// Get export status
router.get(
  '/export/:id/status',
  authenticate,
  param('id').isInt(),
  validate,
  asyncHandler(accountController.getExportStatus)
);

// Delete account
router.delete(
  '/',
  authenticate,
  asyncHandler(accountController.deleteAccount)
);

export default router;
