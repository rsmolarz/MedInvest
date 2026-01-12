/**
 * @medinvest/shared - Validators
 * 
 * Zod schemas for validating data on both web and mobile.
 * Use these for form validation and API request/response validation.
 */

import { z } from 'zod';
import { REACTION_TYPES, DEAL_STAGES, ROOM_SPECIALTIES } from './index';

// =============================================================================
// AUTH VALIDATORS
// =============================================================================

export const emailSchema = z
  .string()
  .min(1, 'Email is required')
  .email('Invalid email address');

export const passwordSchema = z
  .string()
  .min(8, 'Password must be at least 8 characters')
  .regex(/[A-Z]/, 'Password must contain at least one uppercase letter')
  .regex(/[a-z]/, 'Password must contain at least one lowercase letter')
  .regex(/[0-9]/, 'Password must contain at least one number');

export const loginSchema = z.object({
  email: emailSchema,
  password: z.string().min(1, 'Password is required'),
});

export const registerSchema = z.object({
  email: emailSchema,
  password: passwordSchema,
  full_name: z
    .string()
    .min(2, 'Name must be at least 2 characters')
    .max(100, 'Name must be less than 100 characters'),
  specialty: z.string().optional(),
});

export const forgotPasswordSchema = z.object({
  email: emailSchema,
});

export const resetPasswordSchema = z.object({
  token: z.string().min(1, 'Token is required'),
  password: passwordSchema,
  confirm_password: z.string(),
}).refine((data) => data.password === data.confirm_password, {
  message: 'Passwords do not match',
  path: ['confirm_password'],
});

export const changePasswordSchema = z.object({
  current_password: z.string().min(1, 'Current password is required'),
  new_password: passwordSchema,
  confirm_password: z.string(),
}).refine((data) => data.new_password === data.confirm_password, {
  message: 'Passwords do not match',
  path: ['confirm_password'],
});

// =============================================================================
// USER VALIDATORS
// =============================================================================

export const usernameSchema = z
  .string()
  .min(3, 'Username must be at least 3 characters')
  .max(30, 'Username must be less than 30 characters')
  .regex(/^[a-zA-Z0-9_]+$/, 'Username can only contain letters, numbers, and underscores');

export const updateProfileSchema = z.object({
  full_name: z
    .string()
    .min(2, 'Name must be at least 2 characters')
    .max(100, 'Name must be less than 100 characters')
    .optional(),
  username: usernameSchema.optional(),
  bio: z.string().max(500, 'Bio must be less than 500 characters').optional(),
  specialty: z.string().optional(),
  credentials: z.string().max(200).optional(),
  location: z.string().max(100).optional(),
  website: z.string().url('Invalid URL').optional().or(z.literal('')),
});

// =============================================================================
// POST VALIDATORS
// =============================================================================

export const postContentSchema = z
  .string()
  .min(1, 'Post content is required')
  .max(5000, 'Post must be less than 5000 characters');

export const createPostSchema = z.object({
  content: postContentSchema,
  room_id: z.number().positive().optional(),
  is_anonymous: z.boolean().optional(),
  images: z.array(z.string().url()).max(10, 'Maximum 10 images allowed').optional(),
  video_url: z.string().url().optional(),
  poll: z.object({
    question: z.string().min(1).max(150),
    options: z.array(z.string().min(1).max(50)).min(2).max(6),
    duration: z.enum(['1day', '3days', '7days', 'none']).optional(),
    allow_multiple: z.boolean().optional(),
    is_anonymous: z.boolean().optional(),
  }).optional(),
});

export const updatePostSchema = z.object({
  content: postContentSchema.optional(),
});

// =============================================================================
// COMMENT VALIDATORS
// =============================================================================

export const commentContentSchema = z
  .string()
  .min(1, 'Comment cannot be empty')
  .max(2000, 'Comment must be less than 2000 characters');

export const createCommentSchema = z.object({
  content: commentContentSchema,
  parent_id: z.number().positive().optional(),
});

// =============================================================================
// MESSAGE VALIDATORS
// =============================================================================

export const messageContentSchema = z
  .string()
  .min(1, 'Message cannot be empty')
  .max(5000, 'Message must be less than 5000 characters');

export const sendMessageSchema = z.object({
  content: messageContentSchema,
  attachments: z.array(z.string().url()).max(5).optional(),
});

// =============================================================================
// REACTION VALIDATORS
// =============================================================================

export const reactionTypeSchema = z.enum(REACTION_TYPES);

export const reactSchema = z.object({
  type: reactionTypeSchema,
});

// =============================================================================
// POLL VALIDATORS
// =============================================================================

export const pollVoteSchema = z.object({
  option_ids: z.array(z.string()).min(1, 'Select at least one option'),
});

// =============================================================================
// SEARCH VALIDATORS
// =============================================================================

export const searchSchema = z.object({
  query: z.string().min(1, 'Search query is required').max(200),
  type: z.enum(['all', 'posts', 'users', 'rooms', 'deals']).optional(),
  room_id: z.number().positive().optional(),
  date_from: z.string().optional(),
  date_to: z.string().optional(),
  sort_by: z.enum(['relevance', 'recent', 'popular']).optional(),
  page: z.number().positive().optional(),
  limit: z.number().positive().max(100).optional(),
});

// =============================================================================
// REPORT VALIDATORS
// =============================================================================

export const reportReasonSchema = z.enum([
  'spam',
  'harassment',
  'hate_speech',
  'misinformation',
  'inappropriate',
  'violence',
  'self_harm',
  'other',
]);

export const createReportSchema = z.object({
  type: z.enum(['user', 'post', 'comment', 'message']),
  target_id: z.number().positive(),
  reason: reportReasonSchema,
  details: z.string().max(1000).optional(),
});

// =============================================================================
// MUTE VALIDATORS
// =============================================================================

export const muteDurationSchema = z.enum([
  '1hour',
  '8hours',
  '24hours',
  '7days',
  '30days',
  'forever',
]);

export const muteUserSchema = z.object({
  mute_posts: z.boolean().optional(),
  mute_comments: z.boolean().optional(),
  mute_messages: z.boolean().optional(),
  mute_notifications: z.boolean().optional(),
  duration: muteDurationSchema,
});

// =============================================================================
// SETTINGS VALIDATORS
// =============================================================================

export const notificationSettingsSchema = z.object({
  enabled: z.boolean(),
  likes: z.boolean(),
  comments: z.boolean(),
  mentions: z.boolean(),
  follows: z.boolean(),
  direct_messages: z.boolean(),
  message_requests: z.boolean(),
  new_posts: z.boolean(),
  trending_posts: z.boolean(),
  room_activity: z.boolean(),
  new_deals: z.boolean(),
  deal_updates: z.boolean(),
  investment_alerts: z.boolean(),
  announcements: z.boolean(),
  security_alerts: z.boolean(),
  weekly_digest: z.boolean(),
  quiet_hours_enabled: z.boolean(),
  quiet_hours_start: z.string(),
  quiet_hours_end: z.string(),
});

export const contentPreferencesSchema = z.object({
  hide_nsfw: z.boolean(),
  blur_sensitive_images: z.boolean(),
  hide_spoilers: z.boolean(),
  show_trending_posts: z.boolean(),
  show_suggested_users: z.boolean(),
  show_promoted_content: z.boolean(),
  autoplay_videos: z.enum(['always', 'wifi', 'never']),
  reduce_animations: z.boolean(),
  compact_mode: z.boolean(),
  content_languages: z.array(z.string()),
  translate_posts: z.boolean(),
  muted_keywords: z.array(z.string()),
  show_post_metrics: z.boolean(),
  show_user_badges: z.boolean(),
  confirm_before_posting: z.boolean(),
});

export const privacySettingsSchema = z.object({
  profile_visibility: z.enum(['public', 'followers', 'private']),
  allow_messages_from: z.enum(['everyone', 'followers', 'none']),
  show_online_status: z.boolean(),
  show_read_receipts: z.boolean(),
  allow_tagging: z.boolean(),
  allow_mentions: z.boolean(),
});

// =============================================================================
// DEAL VALIDATORS
// =============================================================================

export const dealStageSchema = z.enum(DEAL_STAGES as unknown as [string, ...string[]]);

export const dealFilterSchema = z.object({
  stage: dealStageSchema.optional(),
  sector: z.string().optional(),
  min_investment: z.number().positive().optional(),
  max_investment: z.number().positive().optional(),
  sort_by: z.enum(['recent', 'popular', 'deadline', 'amount']).optional(),
});

export const expressInterestSchema = z.object({
  amount: z.number().positive().optional(),
  message: z.string().max(1000).optional(),
});

// =============================================================================
// EXPORT INFERRED TYPES
// =============================================================================

export type LoginInput = z.infer<typeof loginSchema>;
export type RegisterInput = z.infer<typeof registerSchema>;
export type ForgotPasswordInput = z.infer<typeof forgotPasswordSchema>;
export type ResetPasswordInput = z.infer<typeof resetPasswordSchema>;
export type ChangePasswordInput = z.infer<typeof changePasswordSchema>;
export type UpdateProfileInput = z.infer<typeof updateProfileSchema>;
export type CreatePostInput = z.infer<typeof createPostSchema>;
export type UpdatePostInput = z.infer<typeof updatePostSchema>;
export type CreateCommentInput = z.infer<typeof createCommentSchema>;
export type SendMessageInput = z.infer<typeof sendMessageSchema>;
export type ReactInput = z.infer<typeof reactSchema>;
export type PollVoteInput = z.infer<typeof pollVoteSchema>;
export type SearchInput = z.infer<typeof searchSchema>;
export type CreateReportInput = z.infer<typeof createReportSchema>;
export type MuteUserInput = z.infer<typeof muteUserSchema>;
export type DealFilterInput = z.infer<typeof dealFilterSchema>;
export type ExpressInterestInput = z.infer<typeof expressInterestSchema>;
