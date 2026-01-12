// lib/analytics/index.ts (Web version)
/**
 * Analytics Integration for Web
 * Sentry for error tracking, Mixpanel for product analytics
 */

import * as Sentry from '@sentry/nextjs';
import mixpanel from 'mixpanel-browser';

// =============================================================================
// CONFIGURATION
// =============================================================================

const SENTRY_DSN = process.env.NEXT_PUBLIC_SENTRY_DSN || '';
const MIXPANEL_TOKEN = process.env.NEXT_PUBLIC_MIXPANEL_TOKEN || '';

let isInitialized = false;

// =============================================================================
// INITIALIZATION
// =============================================================================

export function initializeAnalytics() {
  if (isInitialized) return;

  // Initialize Sentry (usually done in sentry.client.config.ts)
  // Already configured in Next.js setup

  // Initialize Mixpanel
  if (MIXPANEL_TOKEN && typeof window !== 'undefined') {
    mixpanel.init(MIXPANEL_TOKEN, {
      debug: process.env.NODE_ENV === 'development',
      track_pageview: true,
      persistence: 'localStorage',
    });
  }

  isInitialized = true;
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
  if (MIXPANEL_TOKEN) {
    mixpanel.identify(userId);
    if (traits) {
      mixpanel.people.set(traits);
    }
  }
}

export function setUserTraits(traits: Record<string, any>) {
  Sentry.setContext('user_traits', traits);
  
  if (MIXPANEL_TOKEN) {
    mixpanel.people.set(traits);
  }
}

export function resetUser() {
  Sentry.setUser(null);
  if (MIXPANEL_TOKEN) {
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
  if (MIXPANEL_TOKEN) {
    mixpanel.track(eventName, properties);
  }

  // Log in dev
  if (process.env.NODE_ENV === 'development') {
    console.log('[Analytics]', eventName, properties);
  }
}

// =============================================================================
// PAGE TRACKING
// =============================================================================

export function trackPageView(pageName: string, properties?: Record<string, any>) {
  trackEvent('Page Viewed', {
    page_name: pageName,
    url: typeof window !== 'undefined' ? window.location.href : '',
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

  trackEvent('Error Occurred', {
    error_name: error.name,
    error_message: error.message,
    ...context,
  });
}

export function captureMessage(message: string, level: Sentry.SeverityLevel = 'info') {
  Sentry.captureMessage(message, level);
}

// =============================================================================
// PREDEFINED EVENTS (Same as mobile)
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
  
  // Deal Events
  dealViewed: (dealId: number, stage: string) => trackEvent('Deal Viewed', { deal_id: dealId, stage }),
  dealWatched: (dealId: number) => trackEvent('Deal Watched', { deal_id: dealId }),
  interestExpressed: (dealId: number, amount?: number) =>
    trackEvent('Interest Expressed', { deal_id: dealId, amount }),
  
  // Search Events
  searchPerformed: (query: string, type: string) =>
    trackEvent('Search Performed', { query, search_type: type }),
  
  // Error Events
  apiError: (endpoint: string, statusCode: number) =>
    trackEvent('API Error', { endpoint, status_code: statusCode }),
};

// =============================================================================
// REACT HOOKS
// =============================================================================

import { useEffect, useRef } from 'react';
import { usePathname } from 'next/navigation';

export function usePageTracking() {
  const pathname = usePathname();
  const prevPathname = useRef<string | null>(null);

  useEffect(() => {
    if (pathname !== prevPathname.current) {
      trackPageView(pathname);
      prevPathname.current = pathname;
    }
  }, [pathname]);
}

// =============================================================================
// SENTRY CONFIGS
// =============================================================================

// sentry.client.config.ts
export const sentryClientConfig = {
  dsn: SENTRY_DSN,
  tracesSampleRate: process.env.NODE_ENV === 'production' ? 0.2 : 1.0,
  replaysSessionSampleRate: 0.1,
  replaysOnErrorSampleRate: 1.0,
  debug: process.env.NODE_ENV === 'development',
};

// sentry.server.config.ts
export const sentryServerConfig = {
  dsn: SENTRY_DSN,
  tracesSampleRate: process.env.NODE_ENV === 'production' ? 0.2 : 1.0,
};
