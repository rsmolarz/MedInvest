/**
 * Search Routes
 */

import { Router } from 'express';
import { query } from 'express-validator';
import { validate } from '../middleware/validate';
import { optionalAuth } from '../middleware/auth';
import { asyncHandler } from '../middleware/error';
import * as searchController from '../controllers/search';

const router = Router();

// Search
router.get(
  '/',
  optionalAuth,
  [
    query('query').trim().isLength({ min: 1, max: 200 }),
    query('type').optional().isIn(['all', 'posts', 'users', 'rooms', 'deals']),
    query('room_id').optional().isInt(),
    query('date_from').optional().isISO8601(),
    query('date_to').optional().isISO8601(),
    query('sort_by').optional().isIn(['relevance', 'recent', 'popular']),
    query('page').optional().isInt({ min: 1 }),
    query('limit').optional().isInt({ min: 1, max: 100 }),
  ],
  validate,
  asyncHandler(searchController.search)
);

// Get trending topics
router.get('/trending', asyncHandler(searchController.getTrending));

// Autocomplete
router.get(
  '/autocomplete',
  optionalAuth,
  query('q').trim().isLength({ min: 1, max: 100 }),
  validate,
  asyncHandler(searchController.autocomplete)
);

export default router;
