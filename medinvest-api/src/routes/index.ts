/**
 * API Routes
 */

import { Router } from 'express';

import authRoutes from './auth';
import userRoutes from './users';
import postRoutes from './posts';
import commentRoutes from './comments';
import roomRoutes from './rooms';
import conversationRoutes from './conversations';
import notificationRoutes from './notifications';
import searchRoutes from './search';
import dealRoutes from './deals';
import settingsRoutes from './settings';
import accountRoutes from './account';
import deviceRoutes from './devices';
import reportRoutes from './reports';
import uploadRoutes from './uploads';

const router = Router();

// Health check
router.get('/', (req, res) => {
  res.json({
    success: true,
    message: 'MedInvest API v1',
    timestamp: new Date().toISOString(),
  });
});

// Mount routes
router.use('/auth', authRoutes);
router.use('/users', userRoutes);
router.use('/posts', postRoutes);
router.use('/comments', commentRoutes);
router.use('/rooms', roomRoutes);
router.use('/conversations', conversationRoutes);
router.use('/notifications', notificationRoutes);
router.use('/search', searchRoutes);
router.use('/deals', dealRoutes);
router.use('/settings', settingsRoutes);
router.use('/account', accountRoutes);
router.use('/devices', deviceRoutes);
router.use('/reports', reportRoutes);
router.use('/uploads', uploadRoutes);

export default router;
