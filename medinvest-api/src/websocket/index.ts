/**
 * WebSocket Setup
 */

import { Server as SocketServer, Socket } from 'socket.io';
import { verifyToken } from '../utils/jwt';
import prisma from '../config/database';
import { logger } from '../utils/logger';

interface AuthenticatedSocket extends Socket {
  userId?: number;
  userEmail?: string;
}

// Store online users
const onlineUsers = new Map<number, Set<string>>(); // userId -> Set<socketId>

export function setupWebSocket(io: SocketServer) {
  // Authentication middleware
  io.use(async (socket: AuthenticatedSocket, next) => {
    try {
      const token = socket.handshake.auth.token || socket.handshake.query.token;
      
      if (!token) {
        return next(new Error('Authentication required'));
      }
      
      const payload = verifyToken(token as string);
      
      if (payload.type !== 'access') {
        return next(new Error('Invalid token type'));
      }
      
      // Verify user exists
      const user = await prisma.user.findUnique({
        where: { id: payload.userId },
        select: { id: true, email: true },
      });
      
      if (!user) {
        return next(new Error('User not found'));
      }
      
      socket.userId = user.id;
      socket.userEmail = user.email;
      
      next();
    } catch (error) {
      next(new Error('Authentication failed'));
    }
  });
  
  io.on('connection', (socket: AuthenticatedSocket) => {
    const userId = socket.userId!;
    
    logger.info(`User ${userId} connected via WebSocket`);
    
    // Track online status
    if (!onlineUsers.has(userId)) {
      onlineUsers.set(userId, new Set());
    }
    onlineUsers.get(userId)!.add(socket.id);
    
    // Join user's personal room
    socket.join(`user:${userId}`);
    
    // Broadcast online status
    broadcastOnlineStatus(io, userId, true);
    
    // Update last seen
    prisma.user.update({
      where: { id: userId },
      data: { last_seen_at: new Date() },
    }).catch(err => logger.error('Failed to update last_seen:', err));
    
    // ===========================================================================
    // EVENT HANDLERS
    // ===========================================================================
    
    // Join conversation room
    socket.on('join_conversation', (conversationId: number) => {
      socket.join(`conversation:${conversationId}`);
      logger.debug(`User ${userId} joined conversation ${conversationId}`);
    });
    
    // Leave conversation room
    socket.on('leave_conversation', (conversationId: number) => {
      socket.leave(`conversation:${conversationId}`);
      logger.debug(`User ${userId} left conversation ${conversationId}`);
    });
    
    // Typing indicator
    socket.on('typing_start', async (conversationId: number) => {
      // Verify user is part of conversation
      const participant = await prisma.conversationParticipant.findFirst({
        where: { conversation_id: conversationId, user_id: userId },
      });
      
      if (participant) {
        socket.to(`conversation:${conversationId}`).emit('typing', {
          conversation_id: conversationId,
          user_id: userId,
          is_typing: true,
        });
      }
    });
    
    socket.on('typing_stop', async (conversationId: number) => {
      socket.to(`conversation:${conversationId}`).emit('typing', {
        conversation_id: conversationId,
        user_id: userId,
        is_typing: false,
      });
    });
    
    // Mark messages as read
    socket.on('mark_read', async (data: { conversationId: number; messageId: number }) => {
      const { conversationId, messageId } = data;
      
      try {
        // Update last read
        await prisma.conversationParticipant.updateMany({
          where: {
            conversation_id: conversationId,
            user_id: userId,
          },
          data: { last_read_at: new Date() },
        });
        
        // Broadcast read receipt
        socket.to(`conversation:${conversationId}`).emit('message_read', {
          conversation_id: conversationId,
          message_id: messageId,
          user_id: userId,
          read_at: new Date().toISOString(),
        });
      } catch (error) {
        logger.error('Failed to mark messages as read:', error);
      }
    });
    
    // Presence ping
    socket.on('ping', () => {
      socket.emit('pong');
    });
    
    // ===========================================================================
    // DISCONNECT
    // ===========================================================================
    
    socket.on('disconnect', () => {
      logger.info(`User ${userId} disconnected from WebSocket`);
      
      // Remove from online users
      const userSockets = onlineUsers.get(userId);
      if (userSockets) {
        userSockets.delete(socket.id);
        if (userSockets.size === 0) {
          onlineUsers.delete(userId);
          broadcastOnlineStatus(io, userId, false);
        }
      }
      
      // Update last seen
      prisma.user.update({
        where: { id: userId },
        data: { last_seen_at: new Date() },
      }).catch(err => logger.error('Failed to update last_seen:', err));
    });
  });
  
  logger.info('✅ WebSocket server initialized');
}

/**
 * Broadcast user online/offline status
 */
function broadcastOnlineStatus(io: SocketServer, userId: number, isOnline: boolean) {
  io.emit(isOnline ? 'user_online' : 'user_offline', { user_id: userId });
}

/**
 * Send message to specific user
 */
export function sendToUser(io: SocketServer, userId: number, event: string, data: any) {
  io.to(`user:${userId}`).emit(event, data);
}

/**
 * Send message to conversation
 */
export function sendToConversation(io: SocketServer, conversationId: number, event: string, data: any) {
  io.to(`conversation:${conversationId}`).emit(event, data);
}

/**
 * Check if user is online
 */
export function isUserOnline(userId: number): boolean {
  return onlineUsers.has(userId) && onlineUsers.get(userId)!.size > 0;
}

/**
 * Get online users count
 */
export function getOnlineUsersCount(): number {
  return onlineUsers.size;
}

export { onlineUsers };
