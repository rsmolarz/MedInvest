/**
 * Conversations Controller
 */

import { Request, Response } from 'express';
import prisma from '../config/database';
import { ApiError } from '../middleware/error';
import { config } from '../config';

const DEFAULT_LIMIT = config.pagination.defaultLimit;

export async function getConversations(req: Request, res: Response) {
  const page = parseInt(req.query.page as string) || 1;
  const limit = parseInt(req.query.limit as string) || DEFAULT_LIMIT;
  const skip = (page - 1) * limit;
  
  const participations = await prisma.conversationParticipant.findMany({
    where: { user_id: req.user!.id },
    include: {
      conversation: {
        include: {
          participants: {
            include: {
              user: {
                select: { id: true, full_name: true, username: true, avatar_url: true, is_verified: true },
              },
            },
          },
          messages: {
            orderBy: { created_at: 'desc' },
            take: 1,
            include: {
              sender: {
                select: { id: true, full_name: true },
              },
            },
          },
        },
      },
    },
    orderBy: { conversation: { updated_at: 'desc' } },
    skip,
    take: limit,
  });
  
  const conversations = participations.map(p => {
    const otherParticipants = p.conversation.participants
      .filter(part => part.user_id !== req.user!.id)
      .map(part => part.user);
    
    return {
      id: p.conversation.id,
      participants: otherParticipants,
      last_message: p.conversation.messages[0] || null,
      unread_count: 0, // TODO: Calculate unread count
      is_muted: p.is_muted,
      created_at: p.conversation.created_at,
      updated_at: p.conversation.updated_at,
    };
  });
  
  res.json({
    success: true,
    data: {
      data: conversations,
      pagination: { page, limit, total: conversations.length, has_more: conversations.length === limit },
    },
  });
}

export async function createConversation(req: Request, res: Response) {
  const { user_id } = req.body;
  
  if (user_id === req.user!.id) {
    throw ApiError.badRequest('Cannot start conversation with yourself');
  }
  
  // Check if conversation already exists
  const existingParticipation = await prisma.conversationParticipant.findFirst({
    where: { user_id: req.user!.id },
    include: {
      conversation: {
        include: {
          participants: true,
        },
      },
    },
  });
  
  // Look for existing conversation with these two users
  const existingConversations = await prisma.conversation.findMany({
    where: {
      participants: {
        every: {
          user_id: { in: [req.user!.id, user_id] },
        },
      },
    },
    include: {
      participants: {
        include: {
          user: {
            select: { id: true, full_name: true, username: true, avatar_url: true },
          },
        },
      },
    },
  });
  
  const existingConvo = existingConversations.find(c => 
    c.participants.length === 2 &&
    c.participants.some(p => p.user_id === req.user!.id) &&
    c.participants.some(p => p.user_id === user_id)
  );
  
  if (existingConvo) {
    return res.json({ success: true, data: existingConvo });
  }
  
  // Create new conversation
  const conversation = await prisma.conversation.create({
    data: {
      participants: {
        create: [
          { user_id: req.user!.id },
          { user_id },
        ],
      },
    },
    include: {
      participants: {
        include: {
          user: {
            select: { id: true, full_name: true, username: true, avatar_url: true },
          },
        },
      },
    },
  });
  
  res.status(201).json({ success: true, data: conversation });
}

export async function getConversation(req: Request, res: Response) {
  const id = parseInt(req.params.id);
  
  const participation = await prisma.conversationParticipant.findFirst({
    where: { conversation_id: id, user_id: req.user!.id },
    include: {
      conversation: {
        include: {
          participants: {
            include: {
              user: {
                select: { id: true, full_name: true, username: true, avatar_url: true, is_verified: true },
              },
            },
          },
        },
      },
    },
  });
  
  if (!participation) {
    throw ApiError.notFound('Conversation not found');
  }
  
  res.json({ success: true, data: participation.conversation });
}

export async function deleteConversation(req: Request, res: Response) {
  const id = parseInt(req.params.id);
  
  // Just remove the participant, don't delete the conversation
  await prisma.conversationParticipant.deleteMany({
    where: { conversation_id: id, user_id: req.user!.id },
  });
  
  res.json({ success: true, message: 'Conversation deleted' });
}

export async function getMessages(req: Request, res: Response) {
  const id = parseInt(req.params.id);
  const page = parseInt(req.query.page as string) || 1;
  const limit = parseInt(req.query.limit as string) || 50;
  const skip = (page - 1) * limit;
  
  // Verify user is part of conversation
  const participation = await prisma.conversationParticipant.findFirst({
    where: { conversation_id: id, user_id: req.user!.id },
  });
  
  if (!participation) {
    throw ApiError.notFound('Conversation not found');
  }
  
  const [messages, total] = await Promise.all([
    prisma.message.findMany({
      where: { conversation_id: id, deleted_at: null },
      include: {
        sender: {
          select: { id: true, full_name: true, username: true, avatar_url: true },
        },
      },
      orderBy: { created_at: 'desc' },
      skip,
      take: limit,
    }),
    prisma.message.count({ where: { conversation_id: id, deleted_at: null } }),
  ]);
  
  res.json({
    success: true,
    data: {
      data: messages.reverse(), // Return in chronological order
      pagination: { page, limit, total, has_more: skip + messages.length < total },
    },
  });
}

export async function sendMessage(req: Request, res: Response) {
  const id = parseInt(req.params.id);
  const { content, attachments } = req.body;
  
  // Verify user is part of conversation
  const participation = await prisma.conversationParticipant.findFirst({
    where: { conversation_id: id, user_id: req.user!.id },
  });
  
  if (!participation) {
    throw ApiError.notFound('Conversation not found');
  }
  
  const message = await prisma.message.create({
    data: {
      conversation_id: id,
      sender_id: req.user!.id,
      content,
      attachments: attachments || [],
    },
    include: {
      sender: {
        select: { id: true, full_name: true, username: true, avatar_url: true },
      },
    },
  });
  
  // Update conversation timestamp
  await prisma.conversation.update({
    where: { id },
    data: { updated_at: new Date() },
  });
  
  // Get Socket.IO instance and emit to conversation room
  const io = req.app.get('io');
  if (io) {
    io.to(`conversation:${id}`).emit('message', message);
  }
  
  // Create notification for other participants
  const otherParticipants = await prisma.conversationParticipant.findMany({
    where: { conversation_id: id, user_id: { not: req.user!.id } },
  });
  
  for (const participant of otherParticipants) {
    await prisma.notification.create({
      data: {
        recipient_id: participant.user_id,
        actor_id: req.user!.id,
        type: 'message',
        title: 'New message',
        body: content.substring(0, 100),
        data: { conversation_id: id, message_id: message.id },
      },
    });
  }
  
  res.status(201).json({ success: true, data: message });
}

export async function markAsRead(req: Request, res: Response) {
  const id = parseInt(req.params.id);
  
  await prisma.conversationParticipant.updateMany({
    where: { conversation_id: id, user_id: req.user!.id },
    data: { last_read_at: new Date() },
  });
  
  res.json({ success: true, message: 'Marked as read' });
}

export async function muteConversation(req: Request, res: Response) {
  const id = parseInt(req.params.id);
  
  await prisma.conversationParticipant.updateMany({
    where: { conversation_id: id, user_id: req.user!.id },
    data: { is_muted: true },
  });
  
  res.json({ success: true, message: 'Conversation muted' });
}

export async function unmuteConversation(req: Request, res: Response) {
  const id = parseInt(req.params.id);
  
  await prisma.conversationParticipant.updateMany({
    where: { conversation_id: id, user_id: req.user!.id },
    data: { is_muted: false },
  });
  
  res.json({ success: true, message: 'Conversation unmuted' });
}
