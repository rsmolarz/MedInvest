/**
 * Upload Routes
 */

import { Router } from 'express';
import multer from 'multer';
import { authenticate } from '../middleware/auth';
import { asyncHandler } from '../middleware/error';
import * as uploadController from '../controllers/uploads';
import { config } from '../config';

const router = Router();

// Configure multer
const storage = multer.memoryStorage();

const upload = multer({
  storage,
  limits: {
    fileSize: config.uploads.maxFileSize,
    files: 10,
  },
  fileFilter: (req, file, cb) => {
    const allowedTypes = [
      ...config.uploads.allowedImageTypes,
      ...config.uploads.allowedVideoTypes,
    ];
    
    if (allowedTypes.includes(file.mimetype)) {
      cb(null, true);
    } else {
      cb(new Error('Invalid file type'));
    }
  },
});

// Upload single image
router.post(
  '/image',
  authenticate,
  upload.single('file'),
  asyncHandler(uploadController.uploadImage)
);

// Upload multiple images
router.post(
  '/images',
  authenticate,
  upload.array('files', 10),
  asyncHandler(uploadController.uploadImages)
);

// Upload video
router.post(
  '/video',
  authenticate,
  upload.single('file'),
  asyncHandler(uploadController.uploadVideo)
);

// Upload avatar
router.post(
  '/avatar',
  authenticate,
  upload.single('file'),
  asyncHandler(uploadController.uploadAvatar)
);

export default router;
