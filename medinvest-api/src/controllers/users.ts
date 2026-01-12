/**
 * Users Controller
 */

import { Request, Response } from 'express';
import prisma from '../config/database';
import { ApiError } from '../middleware/error';
import { hashPassword, comparePassword } from '../utils/password';
import { config } from '../config';

const DEFAULT_LIMIT = config.pagination.defaultLimit;

// Helper to format user response
function formatUser(user: any, currentUserId?: number) {
  return {
    id: user.id,
    email: user.email,
    full_name: user.full_name,
    username: user.username,
    avatar_url: user.avatar_url,
    bio: user.bio,
    specialty: user.specialty,
    credentials: user.credentials,
    location: user.location,
    website: user.website,
    is_verified: user.is_verified,
    is_premium: user.is_premium,
    followers_count: user._count?.followers || 0,
    following_count: user._count?.following || 0,
    posts_count: user._count?.posts || 0,
    created_at: user.created_at,
  };
}

export async function getCurrentUser(req: Request, res: Response) {
  const user = await prisma.user.findUnique({
    where: { id: req.user!.id },
    include: {
      _count: {
        select: {
          followers: true,
          following: true,
          posts: true,
        },
      },
    },
  });
  
  if (!user) {
    throw ApiError.notFound('User not found');
  }
  
  res.json({
    success: true,
    data: formatUser(user),
  });
}

export async function updateProfile(req: Request, res: Response) {
  const { full_name, username, bio, specialty, credentials, location, website } = req.body;
  
  // Check username uniqueness
  if (username) {
    const existingUser = await prisma.user.findFirst({
      where: {
        username,
        id: { not: req.user!.id },
      },
    });
    
    if (existingUser) {
      throw ApiError.conflict('Username already taken');
    }
  }
  
  const user = await prisma.user.update({
    where: { id: req.user!.id },
    data: {
      ...(full_name && { full_name }),
      ...(username && { username }),
      ...(bio !== undefined && { bio }),
      ...(specialty !== undefined && { specialty }),
      ...(credentials !== undefined && { credentials }),
      ...(location !== undefined && { location }),
      ...(website !== undefined && { website }),
    },
    include: {
      _count: {
        select: {
          followers: true,
          following: true,
          posts: true,
        },
      },
    },
  });
  
  res.json({
    success: true,
    data: formatUser(user),
  });
}

export async function changePassword(req: Request, res: Response) {
  const { current_password, new_password } = req.body;
  
  const user = await prisma.user.findUnique({
    where: { id: req.user!.id },
  });
  
  if (!user) {
    throw ApiError.notFound('User not found');
  }
  
  const isValid = await comparePassword(current_password, user.password);
  if (!isValid) {
    throw ApiError.badRequest('Current password is incorrect');
  }
  
  const hashedPassword = await hashPassword(new_password);
  
  await prisma.user.update({
    where: { id: req.user!.id },
    data: { password: hashedPassword },
  });
  
  // Invalidate refresh tokens
  await prisma.refreshToken.deleteMany({
    where: { user_id: req.user!.id },
  });
  
  res.json({
    success: true,
    message: 'Password changed successfully',
  });
}

export async function getUserById(req: Request, res: Response) {
  const id = parseInt(req.params.id);
  
  const user = await prisma.user.findUnique({
    where: { id },
    include: {
      _count: {
        select: {
          followers: true,
          following: true,
          posts: true,
        },
      },
    },
  });
  
  if (!user) {
    throw ApiError.notFound('User not found');
  }
  
  // Get follow status if authenticated
  let isFollowing = false;
  let isBlocked = false;
  let isMuted = false;
  
  if (req.user) {
    const [follow, block, mute] = await Promise.all([
      prisma.follow.findUnique({
        where: { follower_id_following_id: { follower_id: req.user.id, following_id: id } },
      }),
      prisma.block.findUnique({
        where: { blocker_id_blocked_id: { blocker_id: req.user.id, blocked_id: id } },
      }),
      prisma.mute.findUnique({
        where: { muter_id_muted_id: { muter_id: req.user.id, muted_id: id } },
      }),
    ]);
    
    isFollowing = !!follow;
    isBlocked = !!block;
    isMuted = !!mute;
  }
  
  res.json({
    success: true,
    data: {
      ...formatUser(user, req.user?.id),
      is_following: isFollowing,
      is_blocked: isBlocked,
      is_muted: isMuted,
    },
  });
}

export async function getUserByUsername(req: Request, res: Response) {
  const { username } = req.params;
  
  const user = await prisma.user.findUnique({
    where: { username },
    include: {
      _count: {
        select: {
          followers: true,
          following: true,
          posts: true,
        },
      },
    },
  });
  
  if (!user) {
    throw ApiError.notFound('User not found');
  }
  
  res.json({
    success: true,
    data: formatUser(user, req.user?.id),
  });
}

export async function getUserPosts(req: Request, res: Response) {
  const id = parseInt(req.params.id);
  const page = parseInt(req.query.page as string) || 1;
  const limit = parseInt(req.query.limit as string) || DEFAULT_LIMIT;
  const skip = (page - 1) * limit;
  
  const [posts, total] = await Promise.all([
    prisma.post.findMany({
      where: { author_id: id, deleted_at: null },
      include: {
        author: {
          select: {
            id: true,
            full_name: true,
            username: true,
            avatar_url: true,
            specialty: true,
            is_verified: true,
          },
        },
        room: true,
        poll: {
          include: { options: true },
        },
        _count: {
          select: { comments: true, likes: true, reactions: true },
        },
      },
      orderBy: { created_at: 'desc' },
      skip,
      take: limit,
    }),
    prisma.post.count({ where: { author_id: id, deleted_at: null } }),
  ]);
  
  res.json({
    success: true,
    data: {
      data: posts,
      pagination: {
        page,
        limit,
        total,
        has_more: skip + posts.length < total,
      },
    },
  });
}

export async function getPinnedPosts(req: Request, res: Response) {
  const id = parseInt(req.params.id);
  
  const pinnedPosts = await prisma.pinnedPost.findMany({
    where: { user_id: id },
    include: {
      post: {
        include: {
          author: {
            select: {
              id: true,
              full_name: true,
              username: true,
              avatar_url: true,
              is_verified: true,
            },
          },
          _count: {
            select: { comments: true, likes: true },
          },
        },
      },
    },
    orderBy: { order: 'asc' },
    take: 3,
  });
  
  res.json({
    success: true,
    data: pinnedPosts.map(pp => pp.post),
  });
}

export async function followUser(req: Request, res: Response) {
  const followingId = parseInt(req.params.id);
  const followerId = req.user!.id;
  
  if (followerId === followingId) {
    throw ApiError.badRequest('Cannot follow yourself');
  }
  
  // Check if already following
  const existing = await prisma.follow.findUnique({
    where: { follower_id_following_id: { follower_id: followerId, following_id: followingId } },
  });
  
  if (existing) {
    throw ApiError.conflict('Already following this user');
  }
  
  await prisma.follow.create({
    data: { follower_id: followerId, following_id: followingId },
  });
  
  // Create notification
  await prisma.notification.create({
    data: {
      recipient_id: followingId,
      actor_id: followerId,
      type: 'follow',
      title: 'New follower',
      body: 'Someone started following you',
      data: { user_id: followerId },
    },
  });
  
  res.json({
    success: true,
    message: 'Following user',
  });
}

export async function unfollowUser(req: Request, res: Response) {
  const followingId = parseInt(req.params.id);
  const followerId = req.user!.id;
  
  await prisma.follow.deleteMany({
    where: { follower_id: followerId, following_id: followingId },
  });
  
  res.json({
    success: true,
    message: 'Unfollowed user',
  });
}

export async function getFollowers(req: Request, res: Response) {
  const id = parseInt(req.params.id);
  const page = parseInt(req.query.page as string) || 1;
  const limit = parseInt(req.query.limit as string) || DEFAULT_LIMIT;
  const skip = (page - 1) * limit;
  
  const [followers, total] = await Promise.all([
    prisma.follow.findMany({
      where: { following_id: id },
      include: {
        follower: {
          select: {
            id: true,
            full_name: true,
            username: true,
            avatar_url: true,
            specialty: true,
            is_verified: true,
          },
        },
      },
      skip,
      take: limit,
    }),
    prisma.follow.count({ where: { following_id: id } }),
  ]);
  
  res.json({
    success: true,
    data: {
      data: followers.map(f => f.follower),
      pagination: {
        page,
        limit,
        total,
        has_more: skip + followers.length < total,
      },
    },
  });
}

export async function getFollowing(req: Request, res: Response) {
  const id = parseInt(req.params.id);
  const page = parseInt(req.query.page as string) || 1;
  const limit = parseInt(req.query.limit as string) || DEFAULT_LIMIT;
  const skip = (page - 1) * limit;
  
  const [following, total] = await Promise.all([
    prisma.follow.findMany({
      where: { follower_id: id },
      include: {
        following: {
          select: {
            id: true,
            full_name: true,
            username: true,
            avatar_url: true,
            specialty: true,
            is_verified: true,
          },
        },
      },
      skip,
      take: limit,
    }),
    prisma.follow.count({ where: { follower_id: id } }),
  ]);
  
  res.json({
    success: true,
    data: {
      data: following.map(f => f.following),
      pagination: {
        page,
        limit,
        total,
        has_more: skip + following.length < total,
      },
    },
  });
}

export async function blockUser(req: Request, res: Response) {
  const blockedId = parseInt(req.params.id);
  const blockerId = req.user!.id;
  
  if (blockerId === blockedId) {
    throw ApiError.badRequest('Cannot block yourself');
  }
  
  await prisma.$transaction([
    // Create block
    prisma.block.upsert({
      where: { blocker_id_blocked_id: { blocker_id: blockerId, blocked_id: blockedId } },
      create: { blocker_id: blockerId, blocked_id: blockedId },
      update: {},
    }),
    // Remove follows
    prisma.follow.deleteMany({
      where: {
        OR: [
          { follower_id: blockerId, following_id: blockedId },
          { follower_id: blockedId, following_id: blockerId },
        ],
      },
    }),
  ]);
  
  res.json({
    success: true,
    message: 'User blocked',
  });
}

export async function unblockUser(req: Request, res: Response) {
  const blockedId = parseInt(req.params.id);
  const blockerId = req.user!.id;
  
  await prisma.block.deleteMany({
    where: { blocker_id: blockerId, blocked_id: blockedId },
  });
  
  res.json({
    success: true,
    message: 'User unblocked',
  });
}

export async function getBlockedUsers(req: Request, res: Response) {
  const blocks = await prisma.block.findMany({
    where: { blocker_id: req.user!.id },
    include: {
      blocked: {
        select: {
          id: true,
          full_name: true,
          username: true,
          avatar_url: true,
        },
      },
    },
  });
  
  res.json({
    success: true,
    data: blocks.map(b => b.blocked),
  });
}

export async function muteUser(req: Request, res: Response) {
  const mutedId = parseInt(req.params.id);
  const muterId = req.user!.id;
  const { mute_posts, mute_comments, mute_messages, mute_notifications, duration } = req.body;
  
  // Calculate expiry
  let expiresAt: Date | null = null;
  if (duration !== 'forever') {
    const hours: Record<string, number> = {
      '1hour': 1,
      '8hours': 8,
      '24hours': 24,
      '7days': 168,
      '30days': 720,
    };
    expiresAt = new Date(Date.now() + hours[duration] * 60 * 60 * 1000);
  }
  
  await prisma.mute.upsert({
    where: { muter_id_muted_id: { muter_id: muterId, muted_id: mutedId } },
    create: {
      muter_id: muterId,
      muted_id: mutedId,
      mute_posts: mute_posts ?? true,
      mute_comments: mute_comments ?? true,
      mute_messages: mute_messages ?? true,
      mute_notifications: mute_notifications ?? true,
      expires_at: expiresAt,
    },
    update: {
      mute_posts: mute_posts ?? true,
      mute_comments: mute_comments ?? true,
      mute_messages: mute_messages ?? true,
      mute_notifications: mute_notifications ?? true,
      expires_at: expiresAt,
    },
  });
  
  res.json({
    success: true,
    message: 'User muted',
  });
}

export async function unmuteUser(req: Request, res: Response) {
  const mutedId = parseInt(req.params.id);
  
  await prisma.mute.deleteMany({
    where: { muter_id: req.user!.id, muted_id: mutedId },
  });
  
  res.json({
    success: true,
    message: 'User unmuted',
  });
}

export async function getMutedUsers(req: Request, res: Response) {
  const mutes = await prisma.mute.findMany({
    where: { muter_id: req.user!.id },
    include: {
      muted: {
        select: {
          id: true,
          full_name: true,
          username: true,
          avatar_url: true,
        },
      },
    },
  });
  
  res.json({
    success: true,
    data: mutes.map(m => ({
      ...m.muted,
      mute_settings: {
        mute_posts: m.mute_posts,
        mute_comments: m.mute_comments,
        mute_messages: m.mute_messages,
        mute_notifications: m.mute_notifications,
        expires_at: m.expires_at,
      },
    })),
  });
}
