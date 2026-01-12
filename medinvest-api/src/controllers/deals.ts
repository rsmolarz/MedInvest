/**
 * Deals Controller
 */

import { Request, Response } from 'express';
import prisma from '../config/database';
import { ApiError } from '../middleware/error';
import { config } from '../config';

const DEFAULT_LIMIT = config.pagination.defaultLimit;

export async function getDeals(req: Request, res: Response) {
  const page = parseInt(req.query.page as string) || 1;
  const limit = parseInt(req.query.limit as string) || DEFAULT_LIMIT;
  const stage = req.query.stage as string;
  const sector = req.query.sector as string;
  const skip = (page - 1) * limit;
  
  const where: any = { is_active: true };
  if (stage) where.stage = stage;
  if (sector) where.sector = sector;
  
  const [deals, total] = await Promise.all([
    prisma.deal.findMany({
      where,
      include: { documents: true },
      orderBy: [{ is_featured: 'desc' }, { created_at: 'desc' }],
      skip,
      take: limit,
    }),
    prisma.deal.count({ where }),
  ]);
  
  // Get watch status
  let watchedIds = new Set<number>();
  if (req.user) {
    const watches = await prisma.dealWatch.findMany({
      where: { user_id: req.user.id, deal_id: { in: deals.map(d => d.id) } },
    });
    watchedIds = new Set(watches.map(w => w.deal_id));
  }
  
  const formattedDeals = deals.map(deal => ({
    ...deal,
    is_watching: watchedIds.has(deal.id),
    investors_count: 0,
  }));
  
  res.json({
    success: true,
    data: { data: formattedDeals, pagination: { page, limit, total, has_more: skip + deals.length < total } },
  });
}

export async function getDeal(req: Request, res: Response) {
  const id = parseInt(req.params.id);
  
  const deal = await prisma.deal.findUnique({
    where: { id },
    include: { documents: true },
  });
  
  if (!deal) {
    throw ApiError.notFound('Deal not found');
  }
  
  let isWatching = false;
  if (req.user) {
    const watch = await prisma.dealWatch.findUnique({
      where: { deal_id_user_id: { deal_id: id, user_id: req.user.id } },
    });
    isWatching = !!watch;
  }
  
  res.json({ success: true, data: { ...deal, is_watching: isWatching } });
}

export async function watchDeal(req: Request, res: Response) {
  const id = parseInt(req.params.id);
  
  await prisma.dealWatch.upsert({
    where: { deal_id_user_id: { deal_id: id, user_id: req.user!.id } },
    create: { deal_id: id, user_id: req.user!.id },
    update: {},
  });
  
  res.json({ success: true, message: 'Deal added to watchlist' });
}

export async function unwatchDeal(req: Request, res: Response) {
  const id = parseInt(req.params.id);
  
  await prisma.dealWatch.deleteMany({
    where: { deal_id: id, user_id: req.user!.id },
  });
  
  res.json({ success: true, message: 'Deal removed from watchlist' });
}

export async function expressInterest(req: Request, res: Response) {
  const id = parseInt(req.params.id);
  const { amount, message } = req.body;
  
  await prisma.dealInterest.upsert({
    where: { deal_id_user_id: { deal_id: id, user_id: req.user!.id } },
    create: { deal_id: id, user_id: req.user!.id, amount, message },
    update: { amount, message },
  });
  
  res.json({ success: true, message: 'Interest expressed' });
}
