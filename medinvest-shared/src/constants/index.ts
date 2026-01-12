/**
 * @medinvest/shared - Constants
 * 
 * All shared constants used across web and mobile apps.
 */

// =============================================================================
// API
// =============================================================================

export const API_VERSION = 'v1';

// =============================================================================
// PAGINATION
// =============================================================================

export const DEFAULT_PAGE_SIZE = 20;
export const MAX_PAGE_SIZE = 100;

// =============================================================================
// CONTENT LIMITS
// =============================================================================

export const LIMITS = {
  // Posts
  POST_CONTENT_MAX: 5000,
  POST_IMAGES_MAX: 10,
  POST_VIDEO_MAX_MB: 100,
  
  // Comments
  COMMENT_CONTENT_MAX: 2000,
  
  // Messages
  MESSAGE_CONTENT_MAX: 5000,
  MESSAGE_ATTACHMENTS_MAX: 5,
  
  // Profile
  BIO_MAX: 500,
  USERNAME_MIN: 3,
  USERNAME_MAX: 30,
  NAME_MIN: 2,
  NAME_MAX: 100,
  
  // Polls
  POLL_QUESTION_MAX: 150,
  POLL_OPTION_MAX: 50,
  POLL_OPTIONS_MIN: 2,
  POLL_OPTIONS_MAX: 6,
  
  // Search
  SEARCH_QUERY_MAX: 200,
  
  // Pins
  PINNED_POSTS_MAX: 3,
  
  // Keywords
  MUTED_KEYWORDS_MAX: 100,
} as const;

// =============================================================================
// TIMEOUTS & INTERVALS
// =============================================================================

export const TIMEOUTS = {
  // API
  API_REQUEST: 30000, // 30 seconds
  FILE_UPLOAD: 120000, // 2 minutes
  
  // UI
  TOAST_DURATION: 3000,
  LOADING_DELAY: 200, // Show loading after this delay
  DEBOUNCE_SEARCH: 300,
  DEBOUNCE_TYPING: 500,
  
  // WebSocket
  WS_RECONNECT_BASE: 1000,
  WS_RECONNECT_MAX: 30000,
  WS_HEARTBEAT: 30000,
  
  // Typing indicator
  TYPING_TIMEOUT: 3000,
} as const;

// =============================================================================
// NOTIFICATION TYPES
// =============================================================================

export const NOTIFICATION_TYPES = {
  LIKE: 'like',
  COMMENT: 'comment',
  REPLY: 'reply',
  MENTION: 'mention',
  FOLLOW: 'follow',
  MESSAGE: 'message',
  DEAL_UPDATE: 'deal_update',
  SYSTEM: 'system',
  ACHIEVEMENT: 'achievement',
} as const;

// =============================================================================
// WEBSOCKET EVENTS
// =============================================================================

export const WS_EVENTS = {
  // Outgoing (client -> server)
  TYPING_START: 'typing_start',
  TYPING_STOP: 'typing_stop',
  MESSAGE_READ: 'message_read',
  PRESENCE_ONLINE: 'presence_online',
  PRESENCE_OFFLINE: 'presence_offline',
  
  // Incoming (server -> client)
  MESSAGE: 'message',
  TYPING: 'typing',
  READ_RECEIPT: 'read_receipt',
  NOTIFICATION: 'notification',
  USER_ONLINE: 'user_online',
  USER_OFFLINE: 'user_offline',
  POST_UPDATED: 'post_updated',
  POST_DELETED: 'post_deleted',
} as const;

// =============================================================================
// ERROR CODES
// =============================================================================

export const ERROR_CODES = {
  // Auth
  UNAUTHORIZED: 'UNAUTHORIZED',
  FORBIDDEN: 'FORBIDDEN',
  TOKEN_EXPIRED: 'TOKEN_EXPIRED',
  INVALID_CREDENTIALS: 'INVALID_CREDENTIALS',
  EMAIL_NOT_VERIFIED: 'EMAIL_NOT_VERIFIED',
  
  // Validation
  VALIDATION_ERROR: 'VALIDATION_ERROR',
  INVALID_INPUT: 'INVALID_INPUT',
  
  // Resources
  NOT_FOUND: 'NOT_FOUND',
  ALREADY_EXISTS: 'ALREADY_EXISTS',
  
  // Rate limiting
  RATE_LIMIT: 'RATE_LIMIT',
  
  // Server
  SERVER_ERROR: 'SERVER_ERROR',
  SERVICE_UNAVAILABLE: 'SERVICE_UNAVAILABLE',
  
  // Network
  NETWORK_ERROR: 'NETWORK_ERROR',
  TIMEOUT: 'TIMEOUT',
} as const;

// =============================================================================
// STORAGE KEYS
// =============================================================================

export const STORAGE_KEYS = {
  // Auth
  AUTH_TOKEN: 'auth_token',
  REFRESH_TOKEN: 'refresh_token',
  USER: 'user',
  
  // Settings
  THEME: 'theme',
  NOTIFICATION_SETTINGS: 'notification_settings',
  CONTENT_PREFERENCES: 'content_preferences',
  
  // Cache
  FEED_CACHE: 'feed_cache',
  USER_CACHE: 'user_cache',
  
  // Features
  ONBOARDING_COMPLETED: 'onboarding_completed',
  COMPLETED_TOURS: 'completed_onboarding_tours',
  RATING_DATA: 'rating_data',
  DRAFT_POSTS: 'draft_posts',
  RECENT_SEARCHES: 'recent_searches',
  SAVED_SEARCHES: 'saved_searches',
  PINNED_POSTS: 'pinned_posts',
  OFFLINE_QUEUE: 'offline_action_queue',
  
  // Widgets (iOS)
  WIDGET_PORTFOLIO: 'widget_data_portfolio',
  WIDGET_NOTIFICATIONS: 'widget_data_notifications',
  WIDGET_QUICK_STATS: 'widget_data_quick_stats',
} as const;

// =============================================================================
// DEEP LINK ROUTES
// =============================================================================

export const DEEP_LINKS = {
  HOME: 'medinvest://home',
  PROFILE: 'medinvest://profile',
  POST: 'medinvest://post', // + /:id
  USER: 'medinvest://user', // + /:id
  ROOM: 'medinvest://room', // + /:id
  DEAL: 'medinvest://deal', // + /:id
  MESSAGES: 'medinvest://messages',
  CONVERSATION: 'medinvest://conversation', // + /:id
  NOTIFICATIONS: 'medinvest://notifications',
  SEARCH: 'medinvest://search',
  TRENDING: 'medinvest://trending',
  PORTFOLIO: 'medinvest://portfolio',
  SETTINGS: 'medinvest://settings',
  NEW_POST: 'medinvest://post/new',
} as const;

// =============================================================================
// COLORS (for consistency across platforms)
// =============================================================================

export const BRAND_COLORS = {
  primary: '#0066FF',
  primaryDark: '#0052CC',
  primaryLight: '#3385FF',
  
  secondary: '#6B7280',
  
  success: '#10B981',
  warning: '#F59E0B',
  error: '#EF4444',
  info: '#3B82F6',
  
  // Reactions
  like: '#3B82F6',
  love: '#EF4444',
  laugh: '#F59E0B',
  wow: '#8B5CF6',
  sad: '#6B7280',
  fire: '#F97316',
  thinking: '#10B981',
  clap: '#EC4899',
} as const;

// =============================================================================
// FEATURE FLAGS
// =============================================================================

export const FEATURES = {
  POLLS: true,
  REACTIONS: true,
  PINNED_POSTS: true,
  ANONYMOUS_POSTS: true,
  DIRECT_MESSAGES: true,
  DEALS: true,
  PREMIUM: true,
  AI_CHAT: true,
  OFFLINE_MODE: true,
  BIOMETRIC_AUTH: true,
  WIDGETS: true, // iOS only
  APP_SHORTCUTS: true,
} as const;

// =============================================================================
// REGEX PATTERNS
// =============================================================================

export const PATTERNS = {
  EMAIL: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
  USERNAME: /^[a-zA-Z0-9_]{3,30}$/,
  MENTION: /@(\w+)/g,
  HASHTAG: /#(\w+)/g,
  URL: /(https?:\/\/[^\s]+)/g,
  PASSWORD_UPPERCASE: /[A-Z]/,
  PASSWORD_LOWERCASE: /[a-z]/,
  PASSWORD_NUMBER: /[0-9]/,
} as const;

// =============================================================================
// VERSION INFO
// =============================================================================

export const SHARED_VERSION = '1.0.0';
