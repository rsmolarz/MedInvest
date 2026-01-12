/**
 * Uploads Controller
 */

import { Request, Response } from 'express';
import sharp from 'sharp';
import path from 'path';
import fs from 'fs/promises';
import { v4 as uuidv4 } from 'uuid';
import { ApiError } from '../middleware/error';
import { config } from '../config';

const UPLOAD_DIR = path.join(process.cwd(), 'uploads');

// Ensure upload directory exists
fs.mkdir(UPLOAD_DIR, { recursive: true }).catch(() => {});

async function saveFile(buffer: Buffer, filename: string): Promise<string> {
  const filepath = path.join(UPLOAD_DIR, filename);
  await fs.writeFile(filepath, buffer);
  return `/uploads/${filename}`;
}

export async function uploadImage(req: Request, res: Response) {
  if (!req.file) {
    throw ApiError.badRequest('No file uploaded');
  }
  
  const filename = `${uuidv4()}.webp`;
  
  // Process and optimize image
  const optimizedBuffer = await sharp(req.file.buffer)
    .resize(1920, 1920, { fit: 'inside', withoutEnlargement: true })
    .webp({ quality: 85 })
    .toBuffer();
  
  const url = await saveFile(optimizedBuffer, filename);
  
  res.json({ success: true, data: { url: `${config.appUrl}${url}` } });
}

export async function uploadImages(req: Request, res: Response) {
  const files = req.files as Express.Multer.File[];
  
  if (!files || files.length === 0) {
    throw ApiError.badRequest('No files uploaded');
  }
  
  const urls: string[] = [];
  
  for (const file of files) {
    const filename = `${uuidv4()}.webp`;
    
    const optimizedBuffer = await sharp(file.buffer)
      .resize(1920, 1920, { fit: 'inside', withoutEnlargement: true })
      .webp({ quality: 85 })
      .toBuffer();
    
    const url = await saveFile(optimizedBuffer, filename);
    urls.push(`${config.appUrl}${url}`);
  }
  
  res.json({ success: true, data: { urls } });
}

export async function uploadVideo(req: Request, res: Response) {
  if (!req.file) {
    throw ApiError.badRequest('No file uploaded');
  }
  
  const ext = path.extname(req.file.originalname) || '.mp4';
  const filename = `${uuidv4()}${ext}`;
  
  const url = await saveFile(req.file.buffer, filename);
  
  res.json({ success: true, data: { url: `${config.appUrl}${url}` } });
}

export async function uploadAvatar(req: Request, res: Response) {
  if (!req.file) {
    throw ApiError.badRequest('No file uploaded');
  }
  
  const filename = `avatar_${req.user!.id}_${Date.now()}.webp`;
  
  // Process avatar - square, smaller size
  const optimizedBuffer = await sharp(req.file.buffer)
    .resize(400, 400, { fit: 'cover' })
    .webp({ quality: 90 })
    .toBuffer();
  
  const url = await saveFile(optimizedBuffer, filename);
  const fullUrl = `${config.appUrl}${url}`;
  
  // Update user avatar
  await (await import('../config/database')).default.user.update({
    where: { id: req.user!.id },
    data: { avatar_url: fullUrl },
  });
  
  res.json({ success: true, data: { url: fullUrl } });
}
