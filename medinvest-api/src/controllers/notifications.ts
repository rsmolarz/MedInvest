/**
 * Notifications Controller
 */

import { Request, Response } from 'express';
import prisma from '../config/database';
import { config } from '../config';

const DEFAULT_LIMIT = config.pagination.defaultLimit;

export async function getNotifications(req: Request, res: Response) {
  const page = parseInt(req.query.page as string) || 1;
  const limit = parseInt(req.query.limit as string) || DEFAULT_LIMIT;
  const skip = (page - 1) * limit;
  
  const [notifications, total, unreadCount] = await Promise.all([
    prisma.notification.findMany({
      where: { recipient_id: req.user!.id },
      include: {
        actor: {
          select: { id: true, full_name: true, username: true, avatar_url: true },
        },
      },
      orderBy: { created_at: 'desc' },
      skip,
      take: limit,
    }),
    prisma.notification.count({ where: { recipient_id: req.user!.id } }),
    prisma.notification.count({ where: { recipient_id: req.user!.id, is_read: false } }),
  ]);
  
  res.json({
    success: true,
    data: {
      data: notifications,
      unread_count: unreadCount,
      pagination: { page, limit, total, has_more: skip + notifications.length < total },
    },
  });
}

export async function getUnreadCount(req: Request, res: Response) {
  const count = await prisma.notification.count({
    where: { recipient_id: req.user!.id, is_read: false },
  });
  
  res.json({ success: true, data: { count } });
}

export async function markAsRead(req: Request, res: Response) {
  const id = parseInt(req.params.id);
  
  await prisma.notification.updateMany({
    where: { id, recipient_id: req.user!.id },
    data: { is_read: true, read_at: new Date() },
  });
  
  res.json({ success: true, message: 'Notification marked as read' });
}

export async function markAllAsRead(req: Request, res: Response) {
  await prisma.notification.updateMany({
    where: { recipient_id: req.user!.id, is_read: false },
    data: { is_read: true, read_at: new Date() },
  });
  
  res.json({ success: true, message: 'All notifications marked as read' });
}
