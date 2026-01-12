/**
 * Devices Controller (Push Notifications)
 */

import { Request, Response } from 'express';
import prisma from '../config/database';

export async function registerDevice(req: Request, res: Response) {
  const { token, platform } = req.body;
  
  // Remove existing device with this token
  await prisma.device.deleteMany({ where: { token } });
  
  // Create new device
  await prisma.device.create({
    data: {
      user_id: req.user!.id,
      token,
      platform,
    },
  });
  
  res.json({ success: true, message: 'Device registered' });
}

export async function unregisterDevice(req: Request, res: Response) {
  const { token } = req.params;
  
  await prisma.device.deleteMany({
    where: { token, user_id: req.user!.id },
  });
  
  res.json({ success: true, message: 'Device unregistered' });
}
