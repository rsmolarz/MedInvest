/**
 * Rooms Controller
 */

import { Request, Response } from 'express';
import prisma from '../config/database';
import { config } from '../config';

const DEFAULT_LIMIT = config.pagination.defaultLimit;

export async function getRooms(req: Request, res: Response) {
  const rooms = await prisma.room.findMany({
    orderBy: { members_count: 'desc' },
  });
  
  let joinedRoomIds = new Set<number>();
  if (req.user) {
    const memberships = await prisma.roomMember.findMany({
      where: { user_id: req.user.id },
      select: { room_id: true },
    });
    joinedRoomIds = new Set(memberships.map(m => m.room_id));
  }
  
  res.json({
    success: true,
    data: rooms.map(room => ({
      ...room,
      is_joined: joinedRoomIds.has(room.id),
    })),
  });
}

export async function getJoinedRooms(req: Request, res: Response) {
  const memberships = await prisma.roomMember.findMany({
    where: { user_id: req.user!.id },
    include: { room: true },
  });
  
  res.json({
    success: true,
    data: memberships.map(m => ({ ...m.room, is_joined: true })),
  });
}

export async function getRoom(req: Request, res: Response) {
  const id = parseInt(req.params.id);
  
  const room = await prisma.room.findUnique({ where: { id } });
  if (!room) {
    return res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'Room not found' } });
  }
  
  let isJoined = false;
  if (req.user) {
    const membership = await prisma.roomMember.findUnique({
      where: { room_id_user_id: { room_id: id, user_id: req.user.id } },
    });
    isJoined = !!membership;
  }
  
  res.json({ success: true, data: { ...room, is_joined: isJoined } });
}

export async function getRoomPosts(req: Request, res: Response) {
  const id = parseInt(req.params.id);
  const page = parseInt(req.query.page as string) || 1;
  const limit = parseInt(req.query.limit as string) || DEFAULT_LIMIT;
  const skip = (page - 1) * limit;
  
  const [posts, total] = await Promise.all([
    prisma.post.findMany({
      where: { room_id: id, deleted_at: null },
      include: {
        author: {
          select: { id: true, full_name: true, username: true, avatar_url: true, is_verified: true },
        },
        _count: { select: { comments: true, likes: true } },
      },
      orderBy: { created_at: 'desc' },
      skip,
      take: limit,
    }),
    prisma.post.count({ where: { room_id: id, deleted_at: null } }),
  ]);
  
  res.json({
    success: true,
    data: { data: posts, pagination: { page, limit, total, has_more: skip + posts.length < total } },
  });
}

export async function joinRoom(req: Request, res: Response) {
  const id = parseInt(req.params.id);
  
  await prisma.roomMember.upsert({
    where: { room_id_user_id: { room_id: id, user_id: req.user!.id } },
    create: { room_id: id, user_id: req.user!.id },
    update: {},
  });
  
  await prisma.room.update({
    where: { id },
    data: { members_count: { increment: 1 } },
  });
  
  res.json({ success: true, message: 'Joined room' });
}

export async function leaveRoom(req: Request, res: Response) {
  const id = parseInt(req.params.id);
  
  const deleted = await prisma.roomMember.deleteMany({
    where: { room_id: id, user_id: req.user!.id },
  });
  
  if (deleted.count > 0) {
    await prisma.room.update({
      where: { id },
      data: { members_count: { decrement: 1 } },
    });
  }
  
  res.json({ success: true, message: 'Left room' });
}
