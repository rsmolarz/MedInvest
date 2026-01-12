/**
 * Deals Routes
 */

import { Router } from 'express';
import { body, param, query } from 'express-validator';
import { validate } from '../middleware/validate';
import { authenticate, optionalAuth } from '../middleware/auth';
import { asyncHandler } from '../middleware/error';
import * as dealController from '../controllers/deals';

const router = Router();

// Get deals
router.get(
  '/',
  optionalAuth,
  [
    query('page').optional().isInt({ min: 1 }),
    query('limit').optional().isInt({ min: 1, max: 100 }),
    query('stage').optional().isIn(['seed', 'series_a', 'series_b', 'series_c', 'growth', 'pre_ipo']),
    query('sector').optional().trim(),
    query('min_investment').optional().isInt({ min: 0 }),
  ],
  validate,
  asyncHandler(dealController.getDeals)
);

// Get deal by ID
router.get(
  '/:id',
  optionalAuth,
  param('id').isInt(),
  validate,
  asyncHandler(dealController.getDeal)
);

// Watch deal
router.post(
  '/:id/watch',
  authenticate,
  param('id').isInt(),
  validate,
  asyncHandler(dealController.watchDeal)
);

// Unwatch deal
router.delete(
  '/:id/watch',
  authenticate,
  param('id').isInt(),
  validate,
  asyncHandler(dealController.unwatchDeal)
);

// Express interest
router.post(
  '/:id/interest',
  authenticate,
  [
    param('id').isInt(),
    body('amount').optional().isInt({ min: 0 }),
    body('message').optional().trim().isLength({ max: 1000 }),
  ],
  validate,
  asyncHandler(dealController.expressInterest)
);

export default router;
