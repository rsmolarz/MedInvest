/**
 * MedInvest Service Worker
 * Handles push notifications and offline caching
 */

const CACHE_NAME = 'medinvest-v1';
const OFFLINE_URL = '/offline.html';

// =============================================================================
// INSTALL - Cache static assets
// =============================================================================
self.addEventListener('install', (event) => {
    console.log('[SW] Installing service worker...');
    
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            console.log('[SW] Caching app shell');
            return cache.addAll([
                '/',
                '/static/icons/icon-192.svg',
                '/static/icons/badge-72.svg'
            ]).catch(err => console.log('[SW] Cache addAll error:', err));
        })
    );
    
    // Activate immediately
    self.skipWaiting();
});

// =============================================================================
// ACTIVATE - Clean up old caches
// =============================================================================
self.addEventListener('activate', (event) => {
    console.log('[SW] Activating service worker...');
    
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames
                    .filter(name => name !== CACHE_NAME)
                    .map(name => caches.delete(name))
            );
        })
    );
    
    // Take control of all pages immediately
    self.clients.claim();
});

// =============================================================================
// PUSH - Handle push notifications
// =============================================================================
self.addEventListener('push', (event) => {
    console.log('[SW] Push received:', event);
    
    let data = {
        title: 'MedInvest',
        body: 'You have a new notification',
        icon: '/static/icons/icon-192.svg',
        badge: '/static/icons/badge-72.svg',
        data: { url: '/' }
    };
    
    // Parse push data
    if (event.data) {
        try {
            const payload = event.data.json();
            data = { ...data, ...payload };
        } catch (e) {
            data.body = event.data.text();
        }
    }
    
    // Show notification
    const options = {
        body: data.body,
        icon: data.icon,
        badge: data.badge,
        tag: data.tag || 'default',
        data: data.data,
        requireInteraction: data.requireInteraction || false,
        actions: data.actions || [
            { action: 'open', title: 'View' },
            { action: 'dismiss', title: 'Dismiss' }
        ],
        vibrate: [100, 50, 100],
        timestamp: Date.now()
    };
    
    event.waitUntil(
        self.registration.showNotification(data.title, options)
    );
});

// =============================================================================
// NOTIFICATION CLICK - Handle notification interactions
// =============================================================================
self.addEventListener('notificationclick', (event) => {
    console.log('[SW] Notification clicked:', event.action);
    
    event.notification.close();
    
    if (event.action === 'dismiss') {
        return;
    }
    
    // Get URL from notification data
    const urlToOpen = event.notification.data?.url || '/';
    
    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true })
            .then((clientList) => {
                // Check if app is already open
                for (const client of clientList) {
                    if (client.url.includes(self.location.origin) && 'focus' in client) {
                        client.navigate(urlToOpen);
                        return client.focus();
                    }
                }
                
                // Open new window
                if (clients.openWindow) {
                    return clients.openWindow(urlToOpen);
                }
            })
    );
});

// =============================================================================
// NOTIFICATION CLOSE - Track dismissed notifications
// =============================================================================
self.addEventListener('notificationclose', (event) => {
    console.log('[SW] Notification closed');
    
    // Optionally track dismissals
    // fetch('/api/notifications/dismissed', { ... });
});

// =============================================================================
// FETCH - Network-first strategy with offline fallback
// =============================================================================
self.addEventListener('fetch', (event) => {
    // Skip non-GET requests
    if (event.request.method !== 'GET') {
        return;
    }
    
    // Skip cross-origin requests
    if (!event.request.url.startsWith(self.location.origin)) {
        return;
    }
    
    event.respondWith(
        fetch(event.request)
            .then((response) => {
                // Cache successful responses
                if (response.status === 200) {
                    const responseClone = response.clone();
                    caches.open(CACHE_NAME).then((cache) => {
                        cache.put(event.request, responseClone);
                    });
                }
                return response;
            })
            .catch(() => {
                // Return cached version if offline
                return caches.match(event.request)
                    .then((cachedResponse) => {
                        return cachedResponse || caches.match(OFFLINE_URL);
                    });
            })
    );
});

// =============================================================================
// MESSAGE - Handle messages from main thread
// =============================================================================
self.addEventListener('message', (event) => {
    console.log('[SW] Message received:', event.data);
    
    if (event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
});

console.log('[SW] Service worker loaded');
