/**
 * Posts Controller
 */

import { Request, Response } from 'express';
import { v4 as uuidv4 } from 'uuid';
import prisma from '../config/database';
import { ApiError } from '../middleware/error';
import { config } from '../config';

const DEFAULT_LIMIT = config.pagination.defaultLimit;

export async function getFeed(req: Request, res: Response) {
  const page = parseInt(req.query.page as string) || 1;
  const limit = parseInt(req.query.limit as string) || DEFAULT_LIMIT;
  const roomId = req.query.room_id ? parseInt(req.query.room_id as string) : undefined;
  const skip = (page - 1) * limit;
  
  const where: any = { deleted_at: null };
  if (roomId) where.room_id = roomId;
  
  const [posts, total] = await Promise.all([
    prisma.post.findMany({
      where,
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
          include: {
            options: {
              include: {
                _count: { select: { votes: true } },
              },
            },
          },
        },
        _count: {
          select: { comments: true, likes: true, reactions: true, bookmarks: true },
        },
        reactions: {
          select: { type: true },
        },
      },
      orderBy: { created_at: 'desc' },
      skip,
      take: limit,
    }),
    prisma.post.count({ where }),
  ]);
  
  // Get user interactions
  let userLikes: Set<number> = new Set();
  let userBookmarks: Set<number> = new Set();
  let userReactions: Map<number, string> = new Map();
  
  if (req.user) {
    const postIds = posts.map(p => p.id);
    
    const [likes, bookmarks, reactions] = await Promise.all([
      prisma.like.findMany({
        where: { user_id: req.user.id, post_id: { in: postIds } },
        select: { post_id: true },
      }),
      prisma.bookmark.findMany({
        where: { user_id: req.user.id, post_id: { in: postIds } },
        select: { post_id: true },
      }),
      prisma.reaction.findMany({
        where: { user_id: req.user.id, post_id: { in: postIds } },
        select: { post_id: true, type: true },
      }),
    ]);
    
    userLikes = new Set(likes.map(l => l.post_id));
    userBookmarks = new Set(bookmarks.map(b => b.post_id));
    reactions.forEach(r => userReactions.set(r.post_id, r.type));
  }
  
  // Format posts
  const formattedPosts = posts.map(post => ({
    id: post.id,
    author: post.is_anonymous ? {
      id: 0,
      full_name: 'Anonymous',
      username: null,
      avatar_url: null,
      is_verified: false,
    } : post.author,
    content: post.content,
    room: post.room,
    is_anonymous: post.is_anonymous,
    images: post.images,
    video_url: post.video_url,
    poll: post.poll ? {
      id: post.poll.id,
      question: post.poll.question,
      options: post.poll.options.map(o => ({
        id: o.id,
        text: o.text,
        votes: o._count.votes,
      })),
      total_votes: post.poll.options.reduce((sum, o) => sum + o._count.votes, 0),
      ends_at: post.poll.ends_at,
      allow_multiple: post.poll.allow_multiple,
      is_anonymous: post.poll.is_anonymous,
    } : null,
    likes_count: post._count.likes,
    comments_count: post._count.comments,
    shares_count: 0,
    views_count: post.views_count,
    is_liked: userLikes.has(post.id),
    is_bookmarked: userBookmarks.has(post.id),
    user_reaction: userReactions.get(post.id),
    reactions: aggregateReactions(post.reactions),
    created_at: post.created_at,
    updated_at: post.updated_at,
  }));
  
  res.json({
    success: true,
    data: {
      data: formattedPosts,
      pagination: {
        page,
        limit,
        total,
        has_more: skip + posts.length < total,
      },
    },
  });
}

function aggregateReactions(reactions: { type: string }[]) {
  const counts: Record<string, number> = {};
  reactions.forEach(r => {
    counts[r.type] = (counts[r.type] || 0) + 1;
  });
  return Object.entries(counts).map(([type, count]) => ({ type, count }));
}

export async function getPost(req: Request, res: Response) {
  const id = parseInt(req.params.id);
  
  const post = await prisma.post.findUnique({
    where: { id },
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
        include: {
          options: {
            include: { _count: { select: { votes: true } } },
          },
        },
      },
      _count: {
        select: { comments: true, likes: true },
      },
    },
  });
  
  if (!post || post.deleted_at) {
    throw ApiError.notFound('Post not found');
  }
  
  // Increment view count
  await prisma.post.update({
    where: { id },
    data: { views_count: { increment: 1 } },
  });
  
  res.json({
    success: true,
    data: post,
  });
}

export async function createPost(req: Request, res: Response) {
  const { content, room_id, is_anonymous, images, video_url, poll } = req.body;
  
  // Create post
  const post = await prisma.post.create({
    data: {
      author_id: req.user!.id,
      content,
      room_id,
      is_anonymous: is_anonymous || false,
      images: images || [],
      video_url,
    },
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
      room: true,
    },
  });
  
  // Create poll if provided
  if (poll) {
    const pollData = await prisma.poll.create({
      data: {
        post_id: post.id,
        question: poll.question,
        allow_multiple: poll.allow_multiple || false,
        is_anonymous: poll.is_anonymous || false,
        ends_at: poll.duration !== 'none' ? calculatePollEndDate(poll.duration) : null,
        options: {
          create: poll.options.map((text: string, index: number) => ({
            id: uuidv4(),
            text,
            order: index,
          })),
        },
      },
      include: { options: true },
    });
    
    (post as any).poll = pollData;
  }
  
  // Extract and save hashtags
  const hashtags = extractHashtags(content);
  if (hashtags.length > 0) {
    for (const tag of hashtags) {
      const hashtag = await prisma.hashtag.upsert({
        where: { tag: tag.toLowerCase() },
        create: { tag: tag.toLowerCase(), posts_count: 1 },
        update: { posts_count: { increment: 1 } },
      });
      
      await prisma.postHashtag.create({
        data: { post_id: post.id, hashtag_id: hashtag.id },
      });
    }
  }
  
  // Extract mentions and create notifications
  const mentions = extractMentions(content);
  if (mentions.length > 0) {
    const users = await prisma.user.findMany({
      where: { username: { in: mentions } },
    });
    
    for (const user of users) {
      await prisma.mention.create({
        data: { post_id: post.id, mentioned_user_id: user.id },
      });
      
      await prisma.notification.create({
        data: {
          recipient_id: user.id,
          actor_id: req.user!.id,
          type: 'mention',
          title: 'You were mentioned',
          body: 'Someone mentioned you in a post',
          data: { post_id: post.id },
        },
      });
    }
  }
  
  res.status(201).json({
    success: true,
    data: post,
  });
}

function calculatePollEndDate(duration: string): Date {
  const now = new Date();
  switch (duration) {
    case '1day': return new Date(now.getTime() + 24 * 60 * 60 * 1000);
    case '3days': return new Date(now.getTime() + 3 * 24 * 60 * 60 * 1000);
    case '7days': return new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);
    default: return new Date(now.getTime() + 24 * 60 * 60 * 1000);
  }
}

function extractHashtags(content: string): string[] {
  const matches = content.match(/#(\w+)/g);
  return matches ? [...new Set(matches.map(m => m.slice(1)))] : [];
}

function extractMentions(content: string): string[] {
  const matches = content.match(/@(\w+)/g);
  return matches ? [...new Set(matches.map(m => m.slice(1)))] : [];
}

export async function updatePost(req: Request, res: Response) {
  const id = parseInt(req.params.id);
  const { content } = req.body;
  
  const post = await prisma.post.findUnique({ where: { id } });
  
  if (!post || post.deleted_at) {
    throw ApiError.notFound('Post not found');
  }
  
  if (post.author_id !== req.user!.id && !req.user!.is_admin) {
    throw ApiError.forbidden('Not authorized to update this post');
  }
  
  const updatedPost = await prisma.post.update({
    where: { id },
    data: { content },
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
    },
  });
  
  res.json({
    success: true,
    data: updatedPost,
  });
}

export async function deletePost(req: Request, res: Response) {
  const id = parseInt(req.params.id);
  
  const post = await prisma.post.findUnique({ where: { id } });
  
  if (!post) {
    throw ApiError.notFound('Post not found');
  }
  
  if (post.author_id !== req.user!.id && !req.user!.is_admin) {
    throw ApiError.forbidden('Not authorized to delete this post');
  }
  
  await prisma.post.update({
    where: { id },
    data: { deleted_at: new Date() },
  });
  
  res.json({
    success: true,
    message: 'Post deleted',
  });
}

export async function likePost(req: Request, res: Response) {
  const postId = parseInt(req.params.id);
  
  await prisma.like.upsert({
    where: { user_id_post_id: { user_id: req.user!.id, post_id: postId } },
    create: { user_id: req.user!.id, post_id: postId },
    update: {},
  });
  
  // Create notification
  const post = await prisma.post.findUnique({ where: { id: postId } });
  if (post && post.author_id !== req.user!.id) {
    await prisma.notification.create({
      data: {
        recipient_id: post.author_id,
        actor_id: req.user!.id,
        type: 'like',
        title: 'New like',
        body: 'Someone liked your post',
        data: { post_id: postId },
      },
    });
  }
  
  res.json({ success: true, message: 'Post liked' });
}

export async function unlikePost(req: Request, res: Response) {
  const postId = parseInt(req.params.id);
  
  await prisma.like.deleteMany({
    where: { user_id: req.user!.id, post_id: postId },
  });
  
  res.json({ success: true, message: 'Like removed' });
}

export async function reactToPost(req: Request, res: Response) {
  const postId = parseInt(req.params.id);
  const { type } = req.body;
  
  await prisma.reaction.upsert({
    where: { user_id_post_id: { user_id: req.user!.id, post_id: postId } },
    create: { user_id: req.user!.id, post_id: postId, type },
    update: { type },
  });
  
  res.json({ success: true, message: 'Reaction added' });
}

export async function removeReaction(req: Request, res: Response) {
  const postId = parseInt(req.params.id);
  
  await prisma.reaction.deleteMany({
    where: { user_id: req.user!.id, post_id: postId },
  });
  
  res.json({ success: true, message: 'Reaction removed' });
}

export async function bookmarkPost(req: Request, res: Response) {
  const postId = parseInt(req.params.id);
  
  await prisma.bookmark.upsert({
    where: { user_id_post_id: { user_id: req.user!.id, post_id: postId } },
    create: { user_id: req.user!.id, post_id: postId },
    update: {},
  });
  
  res.json({ success: true, message: 'Post bookmarked' });
}

export async function removeBookmark(req: Request, res: Response) {
  const postId = parseInt(req.params.id);
  
  await prisma.bookmark.deleteMany({
    where: { user_id: req.user!.id, post_id: postId },
  });
  
  res.json({ success: true, message: 'Bookmark removed' });
}

export async function getBookmarks(req: Request, res: Response) {
  const page = parseInt(req.query.page as string) || 1;
  const limit = parseInt(req.query.limit as string) || DEFAULT_LIMIT;
  const skip = (page - 1) * limit;
  
  const [bookmarks, total] = await Promise.all([
    prisma.bookmark.findMany({
      where: { user_id: req.user!.id },
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
            _count: { select: { comments: true, likes: true } },
          },
        },
      },
      orderBy: { created_at: 'desc' },
      skip,
      take: limit,
    }),
    prisma.bookmark.count({ where: { user_id: req.user!.id } }),
  ]);
  
  res.json({
    success: true,
    data: {
      data: bookmarks.map(b => b.post),
      pagination: { page, limit, total, has_more: skip + bookmarks.length < total },
    },
  });
}

export async function pinPost(req: Request, res: Response) {
  const postId = parseInt(req.params.id);
  
  const post = await prisma.post.findUnique({ where: { id: postId } });
  if (!post || post.author_id !== req.user!.id) {
    throw ApiError.forbidden('Can only pin your own posts');
  }
  
  const pinnedCount = await prisma.pinnedPost.count({ where: { user_id: req.user!.id } });
  if (pinnedCount >= 3) {
    throw ApiError.badRequest('Maximum 3 pinned posts allowed');
  }
  
  await prisma.pinnedPost.upsert({
    where: { user_id_post_id: { user_id: req.user!.id, post_id: postId } },
    create: { user_id: req.user!.id, post_id: postId, order: pinnedCount },
    update: {},
  });
  
  res.json({ success: true, message: 'Post pinned' });
}

export async function unpinPost(req: Request, res: Response) {
  const postId = parseInt(req.params.id);
  
  await prisma.pinnedPost.deleteMany({
    where: { user_id: req.user!.id, post_id: postId },
  });
  
  res.json({ success: true, message: 'Post unpinned' });
}

export async function reportPost(req: Request, res: Response) {
  const postId = parseInt(req.params.id);
  const { reason, details } = req.body;
  
  const post = await prisma.post.findUnique({ where: { id: postId } });
  if (!post) {
    throw ApiError.notFound('Post not found');
  }
  
  await prisma.report.create({
    data: {
      reporter_id: req.user!.id,
      reported_id: post.author_id,
      type: 'post',
      target_id: postId,
      reason,
      details,
    },
  });
  
  res.json({ success: true, message: 'Report submitted' });
}

export async function getComments(req: Request, res: Response) {
  const postId = parseInt(req.params.id);
  const page = parseInt(req.query.page as string) || 1;
  const limit = parseInt(req.query.limit as string) || DEFAULT_LIMIT;
  const skip = (page - 1) * limit;
  
  const [comments, total] = await Promise.all([
    prisma.comment.findMany({
      where: { post_id: postId, parent_id: null, deleted_at: null },
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
        replies: {
          where: { deleted_at: null },
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
            _count: { select: { likes: true } },
          },
          take: 3,
        },
        _count: { select: { likes: true, replies: true } },
      },
      orderBy: { created_at: 'desc' },
      skip,
      take: limit,
    }),
    prisma.comment.count({ where: { post_id: postId, parent_id: null, deleted_at: null } }),
  ]);
  
  res.json({
    success: true,
    data: {
      data: comments,
      pagination: { page, limit, total, has_more: skip + comments.length < total },
    },
  });
}

export async function createComment(req: Request, res: Response) {
  const postId = parseInt(req.params.id);
  const { content, parent_id } = req.body;
  
  const post = await prisma.post.findUnique({ where: { id: postId } });
  if (!post || post.deleted_at) {
    throw ApiError.notFound('Post not found');
  }
  
  const comment = await prisma.comment.create({
    data: {
      post_id: postId,
      author_id: req.user!.id,
      parent_id,
      content,
    },
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
    },
  });
  
  // Create notification
  if (post.author_id !== req.user!.id) {
    await prisma.notification.create({
      data: {
        recipient_id: post.author_id,
        actor_id: req.user!.id,
        type: parent_id ? 'reply' : 'comment',
        title: parent_id ? 'New reply' : 'New comment',
        body: 'Someone commented on your post',
        data: { post_id: postId, comment_id: comment.id },
      },
    });
  }
  
  res.status(201).json({
    success: true,
    data: comment,
  });
}

export async function votePoll(req: Request, res: Response) {
  const postId = parseInt(req.params.postId);
  const pollId = req.params.pollId;
  const { option_ids } = req.body;
  
  const poll = await prisma.poll.findUnique({
    where: { id: pollId },
    include: { options: true },
  });
  
  if (!poll || poll.post_id !== postId) {
    throw ApiError.notFound('Poll not found');
  }
  
  if (poll.ends_at && poll.ends_at < new Date()) {
    throw ApiError.badRequest('Poll has ended');
  }
  
  // Check if already voted
  const existingVote = await prisma.pollVote.findFirst({
    where: { poll_id: pollId, user_id: req.user!.id },
  });
  
  if (existingVote) {
    throw ApiError.badRequest('Already voted');
  }
  
  if (!poll.allow_multiple && option_ids.length > 1) {
    throw ApiError.badRequest('Only one option allowed');
  }
  
  // Create votes
  await prisma.pollVote.createMany({
    data: option_ids.map((optionId: string) => ({
      poll_id: pollId,
      option_id: optionId,
      user_id: req.user!.id,
    })),
  });
  
  res.json({ success: true, message: 'Vote recorded' });
}
