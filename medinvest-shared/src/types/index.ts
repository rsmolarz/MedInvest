/**
 * @medinvest/shared - Types
 * 
 * All TypeScript types shared between web and mobile apps.
 * This is the SINGLE SOURCE OF TRUTH for data structures.
 */

// =============================================================================
// USER TYPES
// =============================================================================

export interface User {
  id: number;
  email: string;
  full_name: string;
  username?: string;
  avatar_url?: string;
  bio?: string;
  specialty?: string;
  credentials?: string;
  location?: string;
  website?: string;
  is_verified: boolean;
  is_premium: boolean;
  is_admin: boolean;
  followers_count: number;
  following_count: number;
  posts_count: number;
  created_at: string;
  updated_at: string;
}

export interface UserProfile extends User {
  is_following: boolean;
  is_blocked: boolean;
  is_muted: boolean;
  mutual_followers_count: number;
}

export interface UserPreview {
  id: number;
  full_name: string;
  username?: string;
  avatar_url?: string;
  specialty?: string;
  is_verified: boolean;
}

// =============================================================================
// POST TYPES
// =============================================================================

export interface Post {
  id: number;
  author: UserPreview;
  content: string;
  room?: Room;
  is_anonymous: boolean;
  images?: string[];
  video_url?: string;
  poll?: Poll;
  likes_count: number;
  comments_count: number;
  shares_count: number;
  views_count: number;
  is_liked: boolean;
  is_bookmarked: boolean;
  is_pinned: boolean;
  reactions: ReactionCount[];
  user_reaction?: ReactionType;
  created_at: string;
  updated_at: string;
}

export interface PostCreate {
  content: string;
  room_id?: number;
  is_anonymous?: boolean;
  images?: string[];
  video_url?: string;
  poll?: PollCreate;
}

export interface PostUpdate {
  content?: string;
}

// =============================================================================
// COMMENT TYPES
// =============================================================================

export interface Comment {
  id: number;
  post_id: number;
  author: UserPreview;
  content: string;
  parent_id?: number;
  replies?: Comment[];
  likes_count: number;
  replies_count: number;
  is_liked: boolean;
  created_at: string;
  updated_at: string;
}

export interface CommentCreate {
  content: string;
  parent_id?: number;
}

// =============================================================================
// REACTION TYPES
// =============================================================================

export const REACTION_TYPES = [
  'like',
  'love',
  'laugh',
  'wow',
  'sad',
  'fire',
  'thinking',
  'clap',
] as const;

export type ReactionType = (typeof REACTION_TYPES)[number];

export interface ReactionCount {
  type: ReactionType;
  count: number;
}

export const REACTION_EMOJIS: Record<ReactionType, string> = {
  like: '👍',
  love: '❤️',
  laugh: '😂',
  wow: '😮',
  sad: '😢',
  fire: '🔥',
  thinking: '🤔',
  clap: '👏',
};

// =============================================================================
// POLL TYPES
// =============================================================================

export interface Poll {
  id: string;
  question: string;
  options: PollOption[];
  total_votes: number;
  ends_at?: string;
  has_voted: boolean;
  user_vote?: string;
  allow_multiple: boolean;
  is_anonymous: boolean;
}

export interface PollOption {
  id: string;
  text: string;
  votes: number;
  percentage?: number;
}

export interface PollCreate {
  question: string;
  options: string[];
  duration?: PollDuration;
  allow_multiple?: boolean;
  is_anonymous?: boolean;
}

export type PollDuration = '1day' | '3days' | '7days' | 'none';

// =============================================================================
// ROOM TYPES
// =============================================================================

export interface Room {
  id: number;
  name: string;
  slug: string;
  description?: string;
  icon?: string;
  color?: string;
  members_count: number;
  posts_count: number;
  is_joined: boolean;
  created_at: string;
}

export const ROOM_SPECIALTIES = [
  'Cardiology',
  'Dermatology',
  'Emergency Medicine',
  'Endocrinology',
  'Family Medicine',
  'Gastroenterology',
  'General Surgery',
  'Hematology',
  'Infectious Disease',
  'Internal Medicine',
  'Nephrology',
  'Neurology',
  'Obstetrics & Gynecology',
  'Oncology',
  'Ophthalmology',
  'Orthopedics',
  'Pediatrics',
  'Psychiatry',
  'Pulmonology',
  'Radiology',
  'Rheumatology',
  'Urology',
] as const;

export type RoomSpecialty = (typeof ROOM_SPECIALTIES)[number];

// =============================================================================
// MESSAGE / DM TYPES
// =============================================================================

export interface DMThread {
  id: number;
  other_user: UserPreview;
  last_message?: DirectMessage;
  unread_count: number;
  created_at: string;
}

export interface DirectMessage {
  id: number;
  thread_id: number;
  sender_id: number;
  sender: UserPreview;
  content: string;
  read_at?: string;
  created_at: string;
}

export interface DirectMessageCreate {
  content: string;
}

// Legacy types for backwards compatibility
export interface Conversation {
  id: number;
  participants: UserPreview[];
  last_message?: Message;
  unread_count: number;
  is_muted: boolean;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: number;
  conversation_id: number;
  sender: UserPreview;
  content: string;
  attachments?: Attachment[];
  status: MessageStatus;
  read_at?: string;
  created_at: string;
}

export type MessageStatus = 'sending' | 'sent' | 'delivered' | 'read' | 'failed';

export interface Attachment {
  id: string;
  type: AttachmentType;
  url: string;
  thumbnail_url?: string;
  filename?: string;
  size?: number;
}

export type AttachmentType = 'image' | 'video' | 'file';

export interface MessageCreate {
  content: string;
  attachments?: string[];
}

// =============================================================================
// NOTIFICATION TYPES
// =============================================================================

export interface Notification {
  id: number;
  type: NotificationType;
  title: string;
  body: string;
  data?: NotificationData;
  is_read: boolean;
  created_at: string;
}

export type NotificationType =
  | 'like'
  | 'comment'
  | 'reply'
  | 'mention'
  | 'follow'
  | 'message'
  | 'deal_update'
  | 'system'
  | 'achievement';

export interface NotificationData {
  post_id?: number;
  comment_id?: number;
  user_id?: number;
  deal_id?: number;
  url?: string;
}

// =============================================================================
// DEAL TYPES
// =============================================================================

export interface Deal {
  id: number;
  title: string;
  company_name: string;
  description: string;
  sector: string;
  stage: DealStage;
  minimum_investment: number;
  target_raise: number;
  current_raise: number;
  valuation?: number;
  logo_url?: string;
  cover_image_url?: string;
  documents?: DealDocument[];
  deadline?: string;
  is_featured: boolean;
  is_watching: boolean;
  investors_count: number;
  created_at: string;
}

export type DealStage =
  | 'seed'
  | 'series_a'
  | 'series_b'
  | 'series_c'
  | 'growth'
  | 'pre_ipo';

export const DEAL_STAGES: DealStage[] = [
  'seed',
  'series_a',
  'series_b',
  'series_c',
  'growth',
  'pre_ipo',
];

export const DEAL_STAGE_LABELS: Record<DealStage, string> = {
  seed: 'Seed',
  series_a: 'Series A',
  series_b: 'Series B',
  series_c: 'Series C',
  growth: 'Growth',
  pre_ipo: 'Pre-IPO',
};

export interface DealDocument {
  id: string;
  name: string;
  type: string;
  url: string;
}

export const DEAL_SECTORS = [
  'Biotech',
  'Digital Health',
  'Medical Devices',
  'Healthcare Services',
  'Pharmaceuticals',
  'Health IT',
  'Diagnostics',
  'Telehealth',
] as const;

export type DealSector = (typeof DEAL_SECTORS)[number];

// =============================================================================
// SEARCH TYPES
// =============================================================================

export interface SearchResults {
  posts: Post[];
  users: UserPreview[];
  rooms: Room[];
  deals: Deal[];
  hashtags: HashtagResult[];
  has_more: boolean;
}

export interface HashtagResult {
  tag: string;
  post_count: number;
}

export interface SearchFilters {
  type?: SearchType;
  room_id?: number;
  date_from?: string;
  date_to?: string;
  sort_by?: SearchSort;
}

export type SearchType = 'all' | 'posts' | 'users' | 'rooms' | 'deals';
export type SearchSort = 'relevance' | 'recent' | 'popular';

// =============================================================================
// PAGINATION
// =============================================================================

export interface PaginatedResponse<T> {
  data: T[];
  pagination: PaginationMeta;
}

export interface PaginationMeta {
  page: number;
  limit: number;
  total: number;
  has_more: boolean;
}

export interface PaginationParams {
  page?: number;
  limit?: number;
}

// =============================================================================
// API RESPONSE TYPES
// =============================================================================

export interface ApiResponse<T> {
  success: true;
  data: T;
  message?: string;
}

export interface ApiError {
  success: false;
  error: {
    code: string;
    message: string;
    details?: Record<string, string[]>;
  };
}

export type ApiResult<T> = ApiResponse<T> | ApiError;

// =============================================================================
// AUTH TYPES
// =============================================================================

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  token: string;
  refresh_token: string;
  user: User;
}

export interface RegisterRequest {
  email: string;
  password: string;
  full_name: string;
  specialty?: string;
}

export interface RegisterResponse {
  user: User;
  message: string;
}

export interface RefreshTokenRequest {
  refresh_token: string;
}

export interface RefreshTokenResponse {
  token: string;
  refresh_token: string;
}

// =============================================================================
// SETTINGS TYPES
// =============================================================================

export interface NotificationSettings {
  enabled: boolean;
  likes: boolean;
  comments: boolean;
  mentions: boolean;
  follows: boolean;
  direct_messages: boolean;
  message_requests: boolean;
  new_posts: boolean;
  trending_posts: boolean;
  room_activity: boolean;
  new_deals: boolean;
  deal_updates: boolean;
  investment_alerts: boolean;
  announcements: boolean;
  security_alerts: boolean;
  weekly_digest: boolean;
  quiet_hours_enabled: boolean;
  quiet_hours_start: string;
  quiet_hours_end: string;
}

export interface ContentPreferences {
  hide_nsfw: boolean;
  blur_sensitive_images: boolean;
  hide_spoilers: boolean;
  show_trending_posts: boolean;
  show_suggested_users: boolean;
  show_promoted_content: boolean;
  autoplay_videos: AutoplayOption;
  reduce_animations: boolean;
  compact_mode: boolean;
  content_languages: string[];
  translate_posts: boolean;
  muted_keywords: string[];
  show_post_metrics: boolean;
  show_user_badges: boolean;
  confirm_before_posting: boolean;
}

export type AutoplayOption = 'always' | 'wifi' | 'never';

export interface PrivacySettings {
  profile_visibility: ProfileVisibility;
  allow_messages_from: MessagePermission;
  show_online_status: boolean;
  show_read_receipts: boolean;
  allow_tagging: boolean;
  allow_mentions: boolean;
}

export type ProfileVisibility = 'public' | 'followers' | 'private';
export type MessagePermission = 'everyone' | 'followers' | 'none';

// =============================================================================
// WEBSOCKET EVENT TYPES
// =============================================================================

export type WebSocketEvent =
  | { type: 'message'; data: Message }
  | { type: 'typing'; data: TypingEvent }
  | { type: 'message_read'; data: MessageReadEvent }
  | { type: 'notification'; data: Notification }
  | { type: 'user_online'; data: { user_id: number } }
  | { type: 'user_offline'; data: { user_id: number } }
  | { type: 'post_updated'; data: { post_id: number; updates: Partial<Post> } }
  | { type: 'post_deleted'; data: { post_id: number } };

export interface TypingEvent {
  conversation_id: number;
  user_id: number;
  is_typing: boolean;
}

export interface MessageReadEvent {
  conversation_id: number;
  message_id: number;
  user_id: number;
}

// =============================================================================
// REPORT TYPES
// =============================================================================

export interface Report {
  id: number;
  type: ReportTargetType;
  target_id: number;
  reporter_id: number;
  reason: ReportReason;
  details?: string;
  status: ReportStatus;
  created_at: string;
}

export type ReportTargetType = 'user' | 'post' | 'comment' | 'message';

export type ReportReason =
  | 'spam'
  | 'harassment'
  | 'hate_speech'
  | 'misinformation'
  | 'inappropriate'
  | 'violence'
  | 'self_harm'
  | 'other';

export type ReportStatus = 'pending' | 'reviewed' | 'resolved' | 'dismissed';

export const REPORT_REASONS: { value: ReportReason; label: string }[] = [
  { value: 'spam', label: 'Spam or misleading' },
  { value: 'harassment', label: 'Harassment or bullying' },
  { value: 'hate_speech', label: 'Hate speech' },
  { value: 'misinformation', label: 'Misinformation' },
  { value: 'inappropriate', label: 'Inappropriate content' },
  { value: 'violence', label: 'Violence or threats' },
  { value: 'self_harm', label: 'Self-harm or suicide' },
  { value: 'other', label: 'Other' },
];

// =============================================================================
// MUTE TYPES
// =============================================================================

export interface MuteSettings {
  user_id: number;
  mute_posts: boolean;
  mute_comments: boolean;
  mute_messages: boolean;
  mute_notifications: boolean;
  duration: MuteDuration;
  expires_at?: string;
}

export type MuteDuration = '1hour' | '8hours' | '24hours' | '7days' | '30days' | 'forever';

export const MUTE_DURATIONS: { value: MuteDuration; label: string }[] = [
  { value: '1hour', label: '1 hour' },
  { value: '8hours', label: '8 hours' },
  { value: '24hours', label: '24 hours' },
  { value: '7days', label: '7 days' },
  { value: '30days', label: '30 days' },
  { value: 'forever', label: 'Forever' },
];
