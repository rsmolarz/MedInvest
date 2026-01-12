/**
 * Stub Controllers
 * These provide basic implementations - extend as needed
 */

// ============================================================================
// COMMENTS CONTROLLER
// ============================================================================
// src/controllers/comments.ts

import { Request, Response } from 'express';
import prisma from '../config/database';
import { ApiError } from '../middleware/error';

export async function updateComment(req: Request, res: Response) {
  const id = parseInt(req.params.id);
  const { content } = req.body;
  
  const comment = await prisma.comment.findUnique({ where: { id } });
  if (!comment || comment.author_id !== req.user!.id) {
    throw ApiError.forbidden('Not authorized');
  }
  
  const updated = await prisma.comment.update({
    where: { id },
    data: { content },
  });
  
  res.json({ success: true, data: updated });
}

export async function deleteComment(req: Request, res: Response) {
  const id = parseInt(req.params.id);
  
  const comment = await prisma.comment.findUnique({ where: { id } });
  if (!comment || (comment.author_id !== req.user!.id && !req.user!.is_admin)) {
    throw ApiError.forbidden('Not authorized');
  }
  
  await prisma.comment.update({
    where: { id },
    data: { deleted_at: new Date() },
  });
  
  res.json({ success: true, message: 'Comment deleted' });
}

export async function likeComment(req: Request, res: Response) {
  const id = parseInt(req.params.id);
  
  await prisma.commentLike.upsert({
    where: { user_id_comment_id: { user_id: req.user!.id, comment_id: id } },
    create: { user_id: req.user!.id, comment_id: id },
    update: {},
  });
  
  res.json({ success: true, message: 'Comment liked' });
}

export async function unlikeComment(req: Request, res: Response) {
  const id = parseInt(req.params.id);
  
  await prisma.commentLike.deleteMany({
    where: { user_id: req.user!.id, comment_id: id },
  });
  
  res.json({ success: true, message: 'Like removed' });
}
