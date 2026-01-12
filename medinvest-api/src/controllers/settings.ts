/**
 * Settings Controller
 */

import { Request, Response } from 'express';
import prisma from '../config/database';

export async function getNotificationSettings(req: Request, res: Response) {
  let settings = await prisma.userSettings.findUnique({
    where: { user_id: req.user!.id },
  });
  
  if (!settings) {
    settings = await prisma.userSettings.create({
      data: { user_id: req.user!.id },
    });
  }
  
  res.json({
    success: true,
    data: {
      enabled: settings.notifications_enabled,
      likes: settings.notify_likes,
      comments: settings.notify_comments,
      mentions: settings.notify_mentions,
      follows: settings.notify_follows,
      direct_messages: settings.notify_messages,
      new_deals: settings.notify_deals,
      quiet_hours_enabled: settings.quiet_hours_enabled,
      quiet_hours_start: settings.quiet_hours_start,
      quiet_hours_end: settings.quiet_hours_end,
    },
  });
}

export async function updateNotificationSettings(req: Request, res: Response) {
  const updates: any = {};
  
  if (req.body.enabled !== undefined) updates.notifications_enabled = req.body.enabled;
  if (req.body.likes !== undefined) updates.notify_likes = req.body.likes;
  if (req.body.comments !== undefined) updates.notify_comments = req.body.comments;
  if (req.body.mentions !== undefined) updates.notify_mentions = req.body.mentions;
  if (req.body.follows !== undefined) updates.notify_follows = req.body.follows;
  if (req.body.direct_messages !== undefined) updates.notify_messages = req.body.direct_messages;
  if (req.body.quiet_hours_enabled !== undefined) updates.quiet_hours_enabled = req.body.quiet_hours_enabled;
  if (req.body.quiet_hours_start !== undefined) updates.quiet_hours_start = req.body.quiet_hours_start;
  if (req.body.quiet_hours_end !== undefined) updates.quiet_hours_end = req.body.quiet_hours_end;
  
  const settings = await prisma.userSettings.upsert({
    where: { user_id: req.user!.id },
    create: { user_id: req.user!.id, ...updates },
    update: updates,
  });
  
  res.json({ success: true, data: settings });
}

export async function getContentPreferences(req: Request, res: Response) {
  let settings = await prisma.userSettings.findUnique({
    where: { user_id: req.user!.id },
  });
  
  if (!settings) {
    settings = await prisma.userSettings.create({
      data: { user_id: req.user!.id },
    });
  }
  
  res.json({
    success: true,
    data: {
      hide_nsfw: settings.hide_nsfw,
      blur_sensitive_images: settings.blur_sensitive_images,
      autoplay_videos: settings.autoplay_videos,
      muted_keywords: settings.muted_keywords,
    },
  });
}

export async function updateContentPreferences(req: Request, res: Response) {
  const updates: any = {};
  
  if (req.body.hide_nsfw !== undefined) updates.hide_nsfw = req.body.hide_nsfw;
  if (req.body.blur_sensitive_images !== undefined) updates.blur_sensitive_images = req.body.blur_sensitive_images;
  if (req.body.autoplay_videos !== undefined) updates.autoplay_videos = req.body.autoplay_videos;
  if (req.body.muted_keywords !== undefined) updates.muted_keywords = req.body.muted_keywords;
  
  const settings = await prisma.userSettings.upsert({
    where: { user_id: req.user!.id },
    create: { user_id: req.user!.id, ...updates },
    update: updates,
  });
  
  res.json({ success: true, data: settings });
}

export async function getPrivacySettings(req: Request, res: Response) {
  let settings = await prisma.userSettings.findUnique({
    where: { user_id: req.user!.id },
  });
  
  if (!settings) {
    settings = await prisma.userSettings.create({
      data: { user_id: req.user!.id },
    });
  }
  
  res.json({
    success: true,
    data: {
      profile_visibility: settings.profile_visibility,
      allow_messages_from: settings.allow_messages_from,
      show_online_status: settings.show_online_status,
      show_read_receipts: settings.show_read_receipts,
    },
  });
}

export async function updatePrivacySettings(req: Request, res: Response) {
  const updates: any = {};
  
  if (req.body.profile_visibility !== undefined) updates.profile_visibility = req.body.profile_visibility;
  if (req.body.allow_messages_from !== undefined) updates.allow_messages_from = req.body.allow_messages_from;
  if (req.body.show_online_status !== undefined) updates.show_online_status = req.body.show_online_status;
  if (req.body.show_read_receipts !== undefined) updates.show_read_receipts = req.body.show_read_receipts;
  
  const settings = await prisma.userSettings.upsert({
    where: { user_id: req.user!.id },
    create: { user_id: req.user!.id, ...updates },
    update: updates,
  });
  
  res.json({ success: true, data: settings });
}
