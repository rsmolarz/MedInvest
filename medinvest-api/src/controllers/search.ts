/**
 * Search Controller
 */

import { Request, Response } from 'express';
import prisma from '../config/database';
import { config } from '../config';

const DEFAULT_LIMIT = config.pagination.defaultLimit;

export async function search(req: Request, res: Response) {
  const query = req.query.query as string;
  const type = (req.query.type as string) || 'all';
  const page = parseInt(req.query.page as string) || 1;
  const limit = parseInt(req.query.limit as string) || DEFAULT_LIMIT;
  
  const results: any = {
    posts: [],
    users: [],
    rooms: [],
    deals: [],
    hashtags: [],
    has_more: false,
  };
  
  const searchTerm = `%${query}%`;
  
  // Search posts
  if (type === 'all' || type === 'posts') {
    results.posts = await prisma.post.findMany({
      where: {
        deleted_at: null,
        content: { contains: query, mode: 'insensitive' },
      },
      include: {
        author: {
          select: { id: true, full_name: true, username: true, avatar_url: true, is_verified: true },
        },
        _count: { select: { comments: true, likes: true } },
      },
      take: limit,
    });
  }
  
  // Search users
  if (type === 'all' || type === 'users') {
    results.users = await prisma.user.findMany({
      where: {
        OR: [
          { full_name: { contains: query, mode: 'insensitive' } },
          { username: { contains: query, mode: 'insensitive' } },
          { specialty: { contains: query, mode: 'insensitive' } },
        ],
      },
      select: {
        id: true,
        full_name: true,
        username: true,
        avatar_url: true,
        specialty: true,
        is_verified: true,
      },
      take: limit,
    });
  }
  
  // Search rooms
  if (type === 'all' || type === 'rooms') {
    results.rooms = await prisma.room.findMany({
      where: {
        OR: [
          { name: { contains: query, mode: 'insensitive' } },
          { description: { contains: query, mode: 'insensitive' } },
        ],
      },
      take: limit,
    });
  }
  
  // Search deals
  if (type === 'all' || type === 'deals') {
    results.deals = await prisma.deal.findMany({
      where: {
        is_active: true,
        OR: [
          { title: { contains: query, mode: 'insensitive' } },
          { company_name: { contains: query, mode: 'insensitive' } },
          { description: { contains: query, mode: 'insensitive' } },
        ],
      },
      take: limit,
    });
  }
  
  // Search hashtags
  if (type === 'all') {
    results.hashtags = await prisma.hashtag.findMany({
      where: { tag: { contains: query.toLowerCase(), mode: 'insensitive' } },
      orderBy: { posts_count: 'desc' },
      take: 10,
    });
  }
  
  res.json({ success: true, data: results });
}

export async function getTrending(req: Request, res: Response) {
  const topics = await prisma.hashtag.findMany({
    orderBy: { posts_count: 'desc' },
    take: 20,
    select: { tag: true, posts_count: true },
  });
  
  res.json({ success: true, data: { topics } });
}

export async function autocomplete(req: Request, res: Response) {
  const query = req.query.q as string;
  
  const [users, hashtags] = await Promise.all([
    prisma.user.findMany({
      where: {
        OR: [
          { full_name: { contains: query, mode: 'insensitive' } },
          { username: { contains: query, mode: 'insensitive' } },
        ],
      },
      select: { id: true, full_name: true, username: true, avatar_url: true },
      take: 5,
    }),
    prisma.hashtag.findMany({
      where: { tag: { startsWith: query.toLowerCase() } },
      orderBy: { posts_count: 'desc' },
      take: 5,
      select: { tag: true },
    }),
  ]);
  
  res.json({
    success: true,
    data: {
      suggestions: [],
      users,
      hashtags: hashtags.map(h => h.tag),
    },
  });
}
