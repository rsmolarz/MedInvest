const PushNotifications = {
    vapidPublicKey: null,
    swRegistration: null,
    
    async init() {
        if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
            console.log('Push notifications not supported');
            return false;
        }
        
        try {
            const response = await fetch('/push/vapid-public-key');
            const data = await response.json();
            this.vapidPublicKey = data.publicKey;
            
            if (!this.vapidPublicKey) {
                console.log('VAPID key not configured');
                return false;
            }
            
            this.swRegistration = await navigator.serviceWorker.register('/static/js/service-worker.js');
            console.log('Service Worker registered');
            
            return true;
        } catch (error) {
            console.error('Push init error:', error);
            return false;
        }
    },
    
    async isSubscribed() {
        if (!this.swRegistration) return false;
        
        const subscription = await this.swRegistration.pushManager.getSubscription();
        return subscription !== null;
    },
    
    async subscribe() {
        if (!this.swRegistration || !this.vapidPublicKey) {
            console.error('Push not initialized');
            return false;
        }
        
        try {
            const permission = await Notification.requestPermission();
            if (permission !== 'granted') {
                console.log('Notification permission denied');
                return false;
            }
            
            const applicationServerKey = this.urlBase64ToUint8Array(this.vapidPublicKey);
            
            const subscription = await this.swRegistration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: applicationServerKey
            });
            
            const response = await fetch('/push/subscribe', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(subscription.toJSON())
            });
            
            const result = await response.json();
            
            if (result.success) {
                console.log('Subscribed to push notifications');
                return true;
            } else {
                console.error('Subscription failed:', result.error);
                return false;
            }
        } catch (error) {
            console.error('Subscribe error:', error);
            return false;
        }
    },
    
    async unsubscribe() {
        if (!this.swRegistration) return false;
        
        try {
            const subscription = await this.swRegistration.pushManager.getSubscription();
            
            if (subscription) {
                await subscription.unsubscribe();
                
                await fetch('/push/unsubscribe', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({endpoint: subscription.endpoint})
                });
            }
            
            console.log('Unsubscribed from push notifications');
            return true;
        } catch (error) {
            console.error('Unsubscribe error:', error);
            return false;
        }
    },
    
    urlBase64ToUint8Array(base64String) {
        const padding = '='.repeat((4 - base64String.length % 4) % 4);
        const base64 = (base64String + padding)
            .replace(/-/g, '+')
            .replace(/_/g, '/');
        
        const rawData = window.atob(base64);
        const outputArray = new Uint8Array(rawData.length);
        
        for (let i = 0; i < rawData.length; ++i) {
            outputArray[i] = rawData.charCodeAt(i);
        }
        return outputArray;
    }
};

document.addEventListener('DOMContentLoaded', async function() {
    const pushToggle = document.getElementById('push-notification-toggle');
    if (!pushToggle) return;
    
    const initialized = await PushNotifications.init();
    if (!initialized) {
        pushToggle.parentElement.style.display = 'none';
        return;
    }
    
    pushToggle.checked = await PushNotifications.isSubscribed();
    
    pushToggle.addEventListener('change', async function() {
        if (this.checked) {
            const success = await PushNotifications.subscribe();
            if (!success) {
                this.checked = false;
            }
        } else {
            await PushNotifications.unsubscribe();
        }
    });
});
