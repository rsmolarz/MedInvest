/**
 * Reports Controller
 */

import { Request, Response } from 'express';
import prisma from '../config/database';

export async function createReport(req: Request, res: Response) {
  const { type, target_id, reason, details } = req.body;
  
  // Get reported user ID if applicable
  let reportedId: number | null = null;
  
  if (type === 'user') {
    reportedId = target_id;
  } else if (type === 'post') {
    const post = await prisma.post.findUnique({ where: { id: target_id } });
    reportedId = post?.author_id || null;
  } else if (type === 'comment') {
    const comment = await prisma.comment.findUnique({ where: { id: target_id } });
    reportedId = comment?.author_id || null;
  }
  
  await prisma.report.create({
    data: {
      reporter_id: req.user!.id,
      reported_id: reportedId,
      type,
      target_id,
      reason,
      details,
    },
  });
  
  res.json({ success: true, message: 'Report submitted' });
}
