/**
 * Settings Routes
 */

import { Router } from 'express';
import { body } from 'express-validator';
import { validate } from '../middleware/validate';
import { authenticate } from '../middleware/auth';
import { asyncHandler } from '../middleware/error';
import * as settingsController from '../controllers/settings';

const router = Router();

// Get notification settings
router.get('/notifications', authenticate, asyncHandler(settingsController.getNotificationSettings));

// Update notification settings
router.put(
  '/notifications',
  authenticate,
  [
    body('enabled').optional().isBoolean(),
    body('likes').optional().isBoolean(),
    body('comments').optional().isBoolean(),
    body('mentions').optional().isBoolean(),
    body('follows').optional().isBoolean(),
    body('direct_messages').optional().isBoolean(),
    body('quiet_hours_enabled').optional().isBoolean(),
    body('quiet_hours_start').optional().matches(/^\d{2}:\d{2}$/),
    body('quiet_hours_end').optional().matches(/^\d{2}:\d{2}$/),
  ],
  validate,
  asyncHandler(settingsController.updateNotificationSettings)
);

// Get content preferences
router.get('/content', authenticate, asyncHandler(settingsController.getContentPreferences));

// Update content preferences
router.put(
  '/content',
  authenticate,
  [
    body('hide_nsfw').optional().isBoolean(),
    body('blur_sensitive_images').optional().isBoolean(),
    body('autoplay_videos').optional().isIn(['always', 'wifi', 'never']),
    body('muted_keywords').optional().isArray(),
  ],
  validate,
  asyncHandler(settingsController.updateContentPreferences)
);

// Get privacy settings
router.get('/privacy', authenticate, asyncHandler(settingsController.getPrivacySettings));

// Update privacy settings
router.put(
  '/privacy',
  authenticate,
  [
    body('profile_visibility').optional().isIn(['public', 'followers', 'private']),
    body('allow_messages_from').optional().isIn(['everyone', 'followers', 'none']),
    body('show_online_status').optional().isBoolean(),
    body('show_read_receipts').optional().isBoolean(),
  ],
  validate,
  asyncHandler(settingsController.updatePrivacySettings)
);

export default router;
