/**
 * @medinvest/shared - API Client
 * 
 * Base API client that works on both web and mobile.
 * Each platform provides its own configuration (token storage, base URL).
 */

import type {
  User,
  UserProfile,
  Post,
  Comment,
  Room,
  Conversation,
  Message,
  DMThread,
  DirectMessage,
  Notification,
  Deal,
  SearchResults,
  SearchFilters,
  PaginatedResponse,
  LoginRequest,
  LoginResponse,
  RegisterRequest,
  RegisterResponse,
  NotificationSettings,
  ContentPreferences,
  PrivacySettings,
} from '../types';
import type {
  CreatePostInput,
  UpdatePostInput,
  CreateCommentInput,
  SendMessageInput,
  MuteUserInput,
  CreateReportInput,
  UpdateProfileInput,
  ChangePasswordInput,
  ExpressInterestInput,
} from '../validators';

// =============================================================================
// TYPES
// =============================================================================

export interface ApiClientConfig {
  /** Base URL for API requests */
  baseUrl: string;
  
  /** Function to get the current auth token */
  getToken: () => Promise<string | null>;
  
  /** Callback when receiving 401 Unauthorized */
  onUnauthorized?: () => void;
  
  /** Callback when receiving any error */
  onError?: (error: ApiClientError) => void;
  
  /** Default timeout in milliseconds */
  timeout?: number;
}

export interface ApiClientError {
  status: number;
  code: string;
  message: string;
  details?: Record<string, string[]>;
}

export interface RequestOptions {
  /** Skip auth header */
  noAuth?: boolean;
  
  /** Custom timeout */
  timeout?: number;
  
  /** Custom headers */
  headers?: Record<string, string>;
}

// =============================================================================
// API CLIENT CLASS
// =============================================================================

export class ApiClient {
  private config: ApiClientConfig;

  constructor(config: ApiClientConfig) {
    this.config = {
      timeout: 30000,
      ...config,
    };
  }

  // ===========================================================================
  // PRIVATE METHODS
  // ===========================================================================

  private async request<T>(
    method: string,
    path: string,
    body?: unknown,
    options: RequestOptions = {}
  ): Promise<T> {
    const url = `${this.config.baseUrl}${path}`;
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    // Add auth token
    if (!options.noAuth) {
      const token = await this.config.getToken();
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }
    }

    // Create abort controller for timeout
    const controller = new AbortController();
    const timeout = options.timeout || this.config.timeout;
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    try {
      const response = await fetch(url, {
        method,
        headers,
        body: body ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      // Handle errors
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        
        const error: ApiClientError = {
          status: response.status,
          code: errorData.error?.code || 'UNKNOWN_ERROR',
          message: errorData.error?.message || response.statusText,
          details: errorData.error?.details,
        };

        if (response.status === 401) {
          this.config.onUnauthorized?.();
        }

        this.config.onError?.(error);
        throw error;
      }

      // Handle empty responses
      if (response.status === 204) {
        return undefined as T;
      }

      return response.json();
    } catch (error) {
      clearTimeout(timeoutId);
      
      if (error instanceof Error && error.name === 'AbortError') {
        const timeoutError: ApiClientError = {
          status: 0,
          code: 'TIMEOUT',
          message: 'Request timed out',
        };
        this.config.onError?.(timeoutError);
        throw timeoutError;
      }
      
      throw error;
    }
  }

  private get<T>(path: string, options?: RequestOptions): Promise<T> {
    return this.request<T>('GET', path, undefined, options);
  }

  private post<T>(path: string, body?: unknown, options?: RequestOptions): Promise<T> {
    return this.request<T>('POST', path, body, options);
  }

  private put<T>(path: string, body?: unknown, options?: RequestOptions): Promise<T> {
    return this.request<T>('PUT', path, body, options);
  }

  private patch<T>(path: string, body?: unknown, options?: RequestOptions): Promise<T> {
    return this.request<T>('PATCH', path, body, options);
  }

  private delete<T>(path: string, options?: RequestOptions): Promise<T> {
    return this.request<T>('DELETE', path, undefined, options);
  }

  // ===========================================================================
  // AUTH
  // ===========================================================================

  async login(data: LoginRequest): Promise<LoginResponse> {
    return this.post('/auth/login', data, { noAuth: true });
  }

  async register(data: RegisterRequest): Promise<RegisterResponse> {
    return this.post('/auth/register', data, { noAuth: true });
  }

  async logout(): Promise<void> {
    return this.post('/auth/logout');
  }

  async refreshToken(refreshToken: string): Promise<{ token: string; refresh_token: string }> {
    return this.post('/auth/refresh', { refresh_token: refreshToken }, { noAuth: true });
  }

  async forgotPassword(email: string): Promise<{ message: string }> {
    return this.post('/auth/forgot-password', { email }, { noAuth: true });
  }

  async resetPassword(token: string, password: string): Promise<{ message: string }> {
    return this.post('/auth/reset-password', { token, password }, { noAuth: true });
  }

  async verifyEmail(token: string): Promise<{ message: string }> {
    return this.post('/auth/verify-email', { token }, { noAuth: true });
  }

  async resendVerification(email: string): Promise<{ message: string }> {
    return this.post('/auth/resend-verification', { email }, { noAuth: true });
  }

  // ===========================================================================
  // USERS
  // ===========================================================================

  async getCurrentUser(): Promise<User> {
    return this.get('/users/me');
  }

  async updateProfile(data: UpdateProfileInput): Promise<User> {
    return this.put('/users/me', data);
  }

  async changePassword(data: ChangePasswordInput): Promise<{ message: string }> {
    return this.put('/users/me/password', data);
  }

  async getUser(id: number): Promise<UserProfile> {
    return this.get(`/users/${id}`);
  }

  async getUserByUsername(username: string): Promise<UserProfile> {
    return this.get(`/users/username/${username}`);
  }

  async followUser(id: number): Promise<void> {
    return this.post(`/users/${id}/follow`);
  }

  async unfollowUser(id: number): Promise<void> {
    return this.delete(`/users/${id}/follow`);
  }

  async getFollowers(id: number, page = 1, limit = 20): Promise<PaginatedResponse<User>> {
    return this.get(`/users/${id}/followers?page=${page}&limit=${limit}`);
  }

  async getFollowing(id: number, page = 1, limit = 20): Promise<PaginatedResponse<User>> {
    return this.get(`/users/${id}/following?page=${page}&limit=${limit}`);
  }

  async blockUser(id: number): Promise<void> {
    return this.post(`/users/${id}/block`);
  }

  async unblockUser(id: number): Promise<void> {
    return this.delete(`/users/${id}/block`);
  }

  async getBlockedUsers(): Promise<User[]> {
    return this.get('/users/blocked');
  }

  async muteUser(id: number, settings: MuteUserInput): Promise<void> {
    return this.post(`/users/${id}/mute`, settings);
  }

  async unmuteUser(id: number): Promise<void> {
    return this.delete(`/users/${id}/mute`);
  }

  async getMutedUsers(): Promise<User[]> {
    return this.get('/users/muted');
  }

  // ===========================================================================
  // POSTS
  // ===========================================================================

  async getFeed(page = 1, limit = 20, roomId?: number): Promise<PaginatedResponse<Post>> {
    let url = `/posts/feed?page=${page}&limit=${limit}`;
    if (roomId) url += `&room_id=${roomId}`;
    return this.get(url);
  }

  async getPost(id: number): Promise<Post> {
    return this.get(`/posts/${id}`);
  }

  async getUserPosts(userId: number, page = 1, limit = 20): Promise<PaginatedResponse<Post>> {
    return this.get(`/users/${userId}/posts?page=${page}&limit=${limit}`);
  }

  async createPost(data: CreatePostInput): Promise<Post> {
    return this.post('/posts', data);
  }

  async updatePost(id: number, data: UpdatePostInput): Promise<Post> {
    return this.put(`/posts/${id}`, data);
  }

  async deletePost(id: number): Promise<void> {
    return this.delete(`/posts/${id}`);
  }

  async likePost(id: number): Promise<void> {
    return this.post(`/posts/${id}/like`);
  }

  async unlikePost(id: number): Promise<void> {
    return this.delete(`/posts/${id}/like`);
  }

  async reactToPost(id: number, type: string): Promise<void> {
    return this.post(`/posts/${id}/react`, { type });
  }

  async removeReaction(id: number): Promise<void> {
    return this.delete(`/posts/${id}/react`);
  }

  async bookmarkPost(id: number): Promise<void> {
    return this.post(`/posts/${id}/bookmark`);
  }

  async unbookmarkPost(id: number): Promise<void> {
    return this.delete(`/posts/${id}/bookmark`);
  }

  async getBookmarks(page = 1, limit = 20): Promise<PaginatedResponse<Post>> {
    return this.get(`/posts/bookmarks?page=${page}&limit=${limit}`);
  }

  async pinPost(id: number): Promise<void> {
    return this.post(`/posts/${id}/pin`);
  }

  async unpinPost(id: number): Promise<void> {
    return this.delete(`/posts/${id}/pin`);
  }

  async getPinnedPosts(userId: number): Promise<Post[]> {
    return this.get(`/users/${userId}/pinned-posts`);
  }

  async reportPost(id: number, data: Omit<CreateReportInput, 'type' | 'target_id'>): Promise<void> {
    return this.post(`/posts/${id}/report`, data);
  }

  // ===========================================================================
  // COMMENTS
  // ===========================================================================

  async getComments(postId: number, page = 1, limit = 20): Promise<PaginatedResponse<Comment>> {
    return this.get(`/posts/${postId}/comments?page=${page}&limit=${limit}`);
  }

  async createComment(postId: number, data: CreateCommentInput): Promise<Comment> {
    return this.post(`/posts/${postId}/comments`, data);
  }

  async updateComment(id: number, content: string): Promise<Comment> {
    return this.put(`/comments/${id}`, { content });
  }

  async deleteComment(id: number): Promise<void> {
    return this.delete(`/comments/${id}`);
  }

  async likeComment(id: number): Promise<void> {
    return this.post(`/comments/${id}/like`);
  }

  async unlikeComment(id: number): Promise<void> {
    return this.delete(`/comments/${id}/like`);
  }

  // ===========================================================================
  // POLLS
  // ===========================================================================

  async votePoll(postId: number, pollId: string, optionIds: string[]): Promise<void> {
    return this.post(`/posts/${postId}/polls/${pollId}/vote`, { option_ids: optionIds });
  }

  // ===========================================================================
  // ROOMS
  // ===========================================================================

  async getRooms(): Promise<Room[]> {
    return this.get('/rooms');
  }

  async getRoom(id: number): Promise<Room> {
    return this.get(`/rooms/${id}`);
  }

  async getRoomPosts(id: number, page = 1, limit = 20): Promise<PaginatedResponse<Post>> {
    return this.get(`/rooms/${id}/posts?page=${page}&limit=${limit}`);
  }

  async joinRoom(id: number): Promise<void> {
    return this.post(`/rooms/${id}/join`);
  }

  async leaveRoom(id: number): Promise<void> {
    return this.delete(`/rooms/${id}/join`);
  }

  async getJoinedRooms(): Promise<Room[]> {
    return this.get('/rooms/joined');
  }

  // ===========================================================================
  // DIRECT MESSAGES (DMs)
  // ===========================================================================

  /** Get all DM threads (inbox) */
  async getDMInbox(): Promise<DMThread[]> {
    return this.get('/messages/');
  }

  /** Get a specific DM thread with messages */
  async getDMThread(threadId: number): Promise<{ thread: DMThread; messages: DirectMessage[]; other_user: User }> {
    return this.get(`/messages/thread/${threadId}`);
  }

  /** Start or continue a conversation with a user */
  async startDMThread(userId: number): Promise<{ thread_id: number }> {
    return this.get(`/messages/new/${userId}`);
  }

  /** Send a direct message */
  async sendDirectMessage(threadId: number, content: string): Promise<DirectMessage> {
    return this.post(`/messages/thread/${threadId}/send`, { content });
  }

  /** Get unread DM count */
  async getDMUnreadCount(): Promise<{ count: number }> {
    return this.get('/messages/api/unread-count');
  }

  // ===========================================================================
  // MESSAGES (Legacy - for backwards compatibility)
  // ===========================================================================

  async getConversations(page = 1, limit = 20): Promise<PaginatedResponse<Conversation>> {
    return this.get(`/conversations?page=${page}&limit=${limit}`);
  }

  async getConversation(id: number): Promise<Conversation> {
    return this.get(`/conversations/${id}`);
  }

  async createConversation(userId: number): Promise<Conversation> {
    return this.post('/conversations', { user_id: userId });
  }

  async deleteConversation(id: number): Promise<void> {
    return this.delete(`/conversations/${id}`);
  }

  async getMessages(conversationId: number, page = 1, limit = 50): Promise<PaginatedResponse<Message>> {
    return this.get(`/conversations/${conversationId}/messages?page=${page}&limit=${limit}`);
  }

  async sendMessage(conversationId: number, data: SendMessageInput): Promise<Message> {
    return this.post(`/conversations/${conversationId}/messages`, data);
  }

  async markConversationRead(id: number): Promise<void> {
    return this.post(`/conversations/${id}/read`);
  }

  async muteConversation(id: number): Promise<void> {
    return this.post(`/conversations/${id}/mute`);
  }

  async unmuteConversation(id: number): Promise<void> {
    return this.delete(`/conversations/${id}/mute`);
  }

  // ===========================================================================
  // NOTIFICATIONS
  // ===========================================================================

  async getNotifications(page = 1, limit = 20): Promise<PaginatedResponse<Notification> & { unread_count: number }> {
    return this.get(`/notifications?page=${page}&limit=${limit}`);
  }

  async markNotificationRead(id: number): Promise<void> {
    return this.post(`/notifications/${id}/read`);
  }

  async markAllNotificationsRead(): Promise<void> {
    return this.post('/notifications/read-all');
  }

  async getUnreadCount(): Promise<{ count: number }> {
    return this.get('/notifications/unread-count');
  }

  // ===========================================================================
  // SEARCH
  // ===========================================================================

  async search(query: string, filters?: SearchFilters, page = 1, limit = 20): Promise<SearchResults> {
    const params = new URLSearchParams({ query, page: String(page), limit: String(limit) });
    if (filters?.type) params.append('type', filters.type);
    if (filters?.room_id) params.append('room_id', String(filters.room_id));
    if (filters?.date_from) params.append('date_from', filters.date_from);
    if (filters?.date_to) params.append('date_to', filters.date_to);
    if (filters?.sort_by) params.append('sort_by', filters.sort_by);
    return this.get(`/search?${params}`);
  }

  async getTrending(): Promise<{ topics: { tag: string; post_count: number }[] }> {
    return this.get('/search/trending');
  }

  async getAutocomplete(query: string): Promise<{
    suggestions: string[];
    users: User[];
    hashtags: string[];
  }> {
    return this.get(`/search/autocomplete?q=${encodeURIComponent(query)}`);
  }

  // ===========================================================================
  // DEALS
  // ===========================================================================

  async getDeals(page = 1, limit = 20, filters?: {
    stage?: string;
    sector?: string;
    min_investment?: number;
  }): Promise<PaginatedResponse<Deal>> {
    const params = new URLSearchParams({ page: String(page), limit: String(limit) });
    if (filters?.stage) params.append('stage', filters.stage);
    if (filters?.sector) params.append('sector', filters.sector);
    if (filters?.min_investment) params.append('min_investment', String(filters.min_investment));
    return this.get(`/deals?${params}`);
  }

  async getDeal(id: number): Promise<Deal> {
    return this.get(`/deals/${id}`);
  }

  async watchDeal(id: number): Promise<void> {
    return this.post(`/deals/${id}/watch`);
  }

  async unwatchDeal(id: number): Promise<void> {
    return this.delete(`/deals/${id}/watch`);
  }

  async expressInterest(id: number, data: ExpressInterestInput): Promise<void> {
    return this.post(`/deals/${id}/interest`, data);
  }

  // ===========================================================================
  // SETTINGS
  // ===========================================================================

  async getNotificationSettings(): Promise<NotificationSettings> {
    return this.get('/settings/notifications');
  }

  async updateNotificationSettings(settings: Partial<NotificationSettings>): Promise<NotificationSettings> {
    return this.put('/settings/notifications', settings);
  }

  async getContentPreferences(): Promise<ContentPreferences> {
    return this.get('/settings/content');
  }

  async updateContentPreferences(preferences: Partial<ContentPreferences>): Promise<ContentPreferences> {
    return this.put('/settings/content', preferences);
  }

  async getPrivacySettings(): Promise<PrivacySettings> {
    return this.get('/settings/privacy');
  }

  async updatePrivacySettings(settings: Partial<PrivacySettings>): Promise<PrivacySettings> {
    return this.put('/settings/privacy', settings);
  }

  // ===========================================================================
  // ACCOUNT
  // ===========================================================================

  async requestDataExport(categories: string[], format: 'json' | 'csv' | 'html'): Promise<{ export_id: string }> {
    return this.post('/account/export', { categories, format });
  }

  async getExportStatus(id: string): Promise<{
    status: string;
    progress: number;
    download_url?: string;
  }> {
    return this.get(`/account/export/${id}/status`);
  }

  async deleteAccount(password: string): Promise<void> {
    return this.delete('/account', { headers: { 'X-Password': password } });
  }

  // ===========================================================================
  // DEVICES (Push Notifications)
  // ===========================================================================

  async registerDevice(token: string, platform: 'ios' | 'android'): Promise<void> {
    return this.post('/devices/register', { token, platform });
  }

  async unregisterDevice(token: string): Promise<void> {
    return this.delete(`/devices/${token}`);
  }

  // ===========================================================================
  // REPORTS
  // ===========================================================================

  async createReport(data: CreateReportInput): Promise<void> {
    return this.post('/reports', data);
  }

  // ===========================================================================
  // APP VERSION
  // ===========================================================================

  async checkAppVersion(
    currentVersion: string,
    platform: 'ios' | 'android'
  ): Promise<{
    latest_version: string;
    minimum_version: string;
    update_required: boolean;
    update_recommended: boolean;
    release_notes?: string[];
  }> {
    return this.get(`/app/version?currentVersion=${currentVersion}&platform=${platform}`);
  }
}

// =============================================================================
// FACTORY FUNCTION
// =============================================================================

export function createApiClient(config: ApiClientConfig): ApiClient {
  return new ApiClient(config);
}
