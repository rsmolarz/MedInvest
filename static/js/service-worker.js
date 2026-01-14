self.addEventListener('push', function(event) {
    if (!event.data) {
        return;
    }
    
    const data = event.data.json();
    
    const options = {
        body: data.body || '',
        icon: data.icon || '/static/images/logo-icon.png',
        badge: '/static/images/badge-icon.png',
        vibrate: [100, 50, 100],
        data: {
            url: data.url || '/',
            dateOfArrival: Date.now(),
            primaryKey: data.id || 1
        },
        actions: data.actions || []
    };
    
    if (data.image) {
        options.image = data.image;
    }
    
    event.waitUntil(
        self.registration.showNotification(data.title || 'MedInvest', options)
    );
});

self.addEventListener('notificationclick', function(event) {
    event.notification.close();
    
    const urlToOpen = event.notification.data.url || '/';
    
    event.waitUntil(
        clients.matchAll({type: 'window', includeUncontrolled: true}).then(function(clientList) {
            for (let i = 0; i < clientList.length; i++) {
                const client = clientList[i];
                if (client.url.includes(self.location.origin) && 'focus' in client) {
                    client.navigate(urlToOpen);
                    return client.focus();
                }
            }
            if (clients.openWindow) {
                return clients.openWindow(urlToOpen);
            }
        })
    );
});

self.addEventListener('install', function(event) {
    self.skipWaiting();
});

self.addEventListener('activate', function(event) {
    event.waitUntil(clients.claim());
});
