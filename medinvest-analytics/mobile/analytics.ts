// lib/analytics/index.ts
/**
 * Analytics Integration
 * Sentry for crash reporting, Mixpanel for product analytics
 */

import * as Sentry from '@sentry/react-native';
import { Mixpanel } from 'mixpanel-react-native';

// =============================================================================
// CONFIGURATION
// =============================================================================

const SENTRY_DSN = process.env.EXPO_PUBLIC_SENTRY_DSN || '';
const MIXPANEL_TOKEN = process.env.EXPO_PUBLIC_MIXPANEL_TOKEN || '';

let mixpanel: Mixpanel | null = null;

// =============================================================================
// INITIALIZATION
// =============================================================================

export function initializeAnalytics() {
  // Initialize Sentry
  if (SENTRY_DSN) {
    Sentry.init({
      dsn: SENTRY_DSN,
      environment: __DEV__ ? 'development' : 'production',
      enableAutoSessionTracking: true,
      sessionTrackingIntervalMillis: 30000,
      tracesSampleRate: __DEV__ ? 1.0 : 0.2,
      attachStacktrace: true,
      enableNative: true,
      enableNativeCrashHandling: true,
      debug: __DEV__,
    });
  }

  // Initialize Mixpanel
  if (MIXPANEL_TOKEN) {
    mixpanel = new Mixpanel(MIXPANEL_TOKEN, true);
    mixpanel.init();
  }
}

// =============================================================================
// USER IDENTIFICATION
// =============================================================================

export function identifyUser(userId: string, traits?: Record<string, any>) {
  // Sentry
  Sentry.setUser({
    id: userId,
    ...traits,
  });

  // Mixpanel
  if (mixpanel) {
    mixpanel.identify(userId);
    if (traits) {
      mixpanel.getPeople().set(traits);
    }
  }
}

export function setUserTraits(traits: Record<string, any>) {
  // Sentry
  Sentry.setContext('user_traits', traits);

  // Mixpanel
  if (mixpanel) {
    mixpanel.getPeople().set(traits);
  }
}

export function resetUser() {
  Sentry.setUser(null);
  if (mixpanel) {
    mixpanel.reset();
  }
}

// =============================================================================
// EVENT TRACKING
// =============================================================================

export function trackEvent(eventName: string, properties?: Record<string, any>) {
  // Sentry breadcrumb
  Sentry.addBreadcrumb({
    category: 'user_action',
    message: eventName,
    data: properties,
    level: 'info',
  });

  // Mixpanel
  if (mixpanel) {
    mixpanel.track(eventName, properties);
  }

  // Log in dev
  if (__DEV__) {
    console.log('[Analytics]', eventName, properties);
  }
}

// =============================================================================
// SCREEN TRACKING
// =============================================================================

export function trackScreen(screenName: string, properties?: Record<string, any>) {
  trackEvent('Screen Viewed', {
    screen_name: screenName,
    ...properties,
  });
}

// =============================================================================
// ERROR TRACKING
// =============================================================================

export function captureError(error: Error, context?: Record<string, any>) {
  Sentry.captureException(error, {
    extra: context,
  });

  // Track in Mixpanel too
  trackEvent('Error Occurred', {
    error_name: error.name,
    error_message: error.message,
    ...context,
  });
}

export function captureMessage(message: string, level: 'info' | 'warning' | 'error' = 'info') {
  Sentry.captureMessage(message, level);
}

// =============================================================================
// PERFORMANCE MONITORING
// =============================================================================

export function startTransaction(name: string, op: string) {
  return Sentry.startTransaction({ name, op });
}

// =============================================================================
// PREDEFINED EVENTS
// =============================================================================

export const Analytics = {
  // Auth Events
  signUp: (method: string) => trackEvent('Sign Up', { method }),
  login: (method: string) => trackEvent('Login', { method }),
  logout: () => trackEvent('Logout'),
  
  // Content Events
  postCreated: (hasImage: boolean, hasPoll: boolean, roomId?: number) =>
    trackEvent('Post Created', { has_image: hasImage, has_poll: hasPoll, room_id: roomId }),
  postViewed: (postId: number) => trackEvent('Post Viewed', { post_id: postId }),
  postLiked: (postId: number) => trackEvent('Post Liked', { post_id: postId }),
  postShared: (postId: number) => trackEvent('Post Shared', { post_id: postId }),
  postBookmarked: (postId: number) => trackEvent('Post Bookmarked', { post_id: postId }),
  commentCreated: (postId: number) => trackEvent('Comment Created', { post_id: postId }),
  
  // Social Events
  userFollowed: (userId: number) => trackEvent('User Followed', { user_id: userId }),
  userUnfollowed: (userId: number) => trackEvent('User Unfollowed', { user_id: userId }),
  userBlocked: (userId: number) => trackEvent('User Blocked', { user_id: userId }),
  userMuted: (userId: number) => trackEvent('User Muted', { user_id: userId }),
  
  // Messaging Events
  conversationStarted: (userId: number) => trackEvent('Conversation Started', { user_id: userId }),
  messageSent: (conversationId: number) => trackEvent('Message Sent', { conversation_id: conversationId }),
  
  // Deal Events
  dealViewed: (dealId: number, stage: string) => trackEvent('Deal Viewed', { deal_id: dealId, stage }),
  dealWatched: (dealId: number) => trackEvent('Deal Watched', { deal_id: dealId }),
  interestExpressed: (dealId: number, amount?: number) =>
    trackEvent('Interest Expressed', { deal_id: dealId, amount }),
  
  // Search Events
  searchPerformed: (query: string, type: string) =>
    trackEvent('Search Performed', { query, search_type: type }),
  
  // Room Events
  roomJoined: (roomId: number, roomName: string) =>
    trackEvent('Room Joined', { room_id: roomId, room_name: roomName }),
  roomLeft: (roomId: number) => trackEvent('Room Left', { room_id: roomId }),
  
  // Notification Events
  notificationReceived: (type: string) => trackEvent('Notification Received', { type }),
  notificationOpened: (type: string) => trackEvent('Notification Opened', { type }),
  pushEnabled: () => trackEvent('Push Notifications Enabled'),
  pushDisabled: () => trackEvent('Push Notifications Disabled'),
  
  // Settings Events
  themeChanged: (theme: string) => trackEvent('Theme Changed', { theme }),
  settingsUpdated: (setting: string) => trackEvent('Settings Updated', { setting }),
  
  // Premium Events
  premiumViewed: () => trackEvent('Premium Page Viewed'),
  premiumPurchased: (plan: string) => trackEvent('Premium Purchased', { plan }),
  
  // App Events
  appOpened: () => trackEvent('App Opened'),
  appBackgrounded: () => trackEvent('App Backgrounded'),
  appForegrounded: () => trackEvent('App Foregrounded'),
  
  // Error Events
  apiError: (endpoint: string, statusCode: number) =>
    trackEvent('API Error', { endpoint, status_code: statusCode }),
};

// =============================================================================
// REACT HOOK
// =============================================================================

import { useEffect, useRef } from 'react';

export function useScreenTracking(screenName: string) {
  const hasTracked = useRef(false);

  useEffect(() => {
    if (!hasTracked.current) {
      trackScreen(screenName);
      hasTracked.current = true;
    }
  }, [screenName]);
}

// =============================================================================
// ERROR BOUNDARY WRAPPER
// =============================================================================

export const SentryErrorBoundary = Sentry.ErrorBoundary;

// =============================================================================
// NAVIGATION INTEGRATION
// =============================================================================

export function createNavigationIntegration() {
  return new Sentry.ReactNavigationInstrumentation();
}
