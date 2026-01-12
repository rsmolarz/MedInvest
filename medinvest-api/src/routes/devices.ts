/**
 * Devices Routes (Push Notifications)
 */

import { Router } from 'express';
import { body, param } from 'express-validator';
import { validate } from '../middleware/validate';
import { authenticate } from '../middleware/auth';
import { asyncHandler } from '../middleware/error';
import * as deviceController from '../controllers/devices';

const router = Router();

// Register device
router.post(
  '/register',
  authenticate,
  [
    body('token').trim().notEmpty(),
    body('platform').isIn(['ios', 'android', 'web']),
  ],
  validate,
  asyncHandler(deviceController.registerDevice)
);

// Unregister device
router.delete(
  '/:token',
  authenticate,
  param('token').trim().notEmpty(),
  validate,
  asyncHandler(deviceController.unregisterDevice)
);

export default router;
