/**
 * Account Controller
 */

import { Request, Response } from 'express';
import prisma from '../config/database';
import { ApiError } from '../middleware/error';
import { comparePassword } from '../utils/password';

export async function requestExport(req: Request, res: Response) {
  const { categories, format } = req.body;
  
  const dataExport = await prisma.dataExport.create({
    data: {
      user_id: req.user!.id,
      categories,
      format,
      status: 'pending',
    },
  });
  
  // TODO: Queue background job to process export
  
  res.json({ success: true, data: { export_id: dataExport.id.toString() } });
}

export async function getExportStatus(req: Request, res: Response) {
  const id = parseInt(req.params.id);
  
  const dataExport = await prisma.dataExport.findFirst({
    where: { id, user_id: req.user!.id },
  });
  
  if (!dataExport) {
    throw ApiError.notFound('Export not found');
  }
  
  res.json({
    success: true,
    data: {
      status: dataExport.status,
      progress: dataExport.progress,
      download_url: dataExport.download_url,
    },
  });
}

export async function deleteAccount(req: Request, res: Response) {
  const password = req.headers['x-password'] as string;
  
  if (!password) {
    throw ApiError.badRequest('Password required to delete account');
  }
  
  const user = await prisma.user.findUnique({ where: { id: req.user!.id } });
  if (!user) {
    throw ApiError.notFound('User not found');
  }
  
  const isValid = await comparePassword(password, user.password);
  if (!isValid) {
    throw ApiError.unauthorized('Invalid password');
  }
  
  // Soft delete - just remove sensitive data
  await prisma.$transaction([
    prisma.user.update({
      where: { id: req.user!.id },
      data: {
        email: `deleted_${req.user!.id}@deleted.com`,
        password: '',
        full_name: 'Deleted User',
        username: null,
        avatar_url: null,
        bio: null,
      },
    }),
    prisma.refreshToken.deleteMany({ where: { user_id: req.user!.id } }),
    prisma.device.deleteMany({ where: { user_id: req.user!.id } }),
  ]);
  
  res.json({ success: true, message: 'Account deleted' });
}
