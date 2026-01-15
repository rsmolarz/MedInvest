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
    const initialized = await PushNotifications.init();
    if (!initialized) return;
    
    const isSubscribed = await PushNotifications.isSubscribed();
    
    // Auto-prompt for push notifications if:
    // 1. User is logged in (check for user-specific elements)
    // 2. Not already subscribed
    // 3. Permission is 'default' (not yet asked)
    // 4. Haven't dismissed the prompt recently
    const isLoggedIn = document.querySelector('.navbar [href*="/profile"]') || 
                       document.querySelector('.navbar [href*="/logout"]') ||
                       document.querySelector('#notificationDropdown');
    
    if (isLoggedIn && !isSubscribed && Notification.permission === 'default') {
        const dismissedAt = localStorage.getItem('pushPromptDismissed');
        const daysSinceDismissed = dismissedAt ? 
            (Date.now() - parseInt(dismissedAt)) / (1000 * 60 * 60 * 24) : 999;
        
        // Show prompt if never dismissed or dismissed more than 7 days ago
        if (daysSinceDismissed > 7) {
            setTimeout(() => {
                showPushPrompt();
            }, 3000); // Wait 3 seconds after page load
        }
    }
    
    // Handle settings page toggle
    const pushToggle = document.getElementById('push-notification-toggle');
    if (pushToggle) {
        pushToggle.checked = isSubscribed;
        
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
    }
});

function showPushPrompt() {
    // Create a subtle prompt banner
    const banner = document.createElement('div');
    banner.id = 'push-prompt-banner';
    banner.innerHTML = `
        <div style="position:fixed;bottom:20px;right:20px;background:#1a5f4a;color:white;padding:16px 20px;border-radius:12px;box-shadow:0 4px 20px rgba(0,0,0,0.2);z-index:9999;max-width:350px;font-family:inherit;">
            <div style="display:flex;align-items:flex-start;gap:12px;">
                <i class="fas fa-bell" style="font-size:24px;margin-top:2px;"></i>
                <div style="flex:1;">
                    <strong style="display:block;margin-bottom:4px;">Stay Updated</strong>
                    <p style="margin:0 0 12px 0;font-size:14px;opacity:0.9;">Get instant notifications for new deals, AMA sessions, and connection requests.</p>
                    <div style="display:flex;gap:8px;">
                        <button id="push-prompt-enable" style="background:white;color:#1a5f4a;border:none;padding:8px 16px;border-radius:6px;cursor:pointer;font-weight:600;font-size:13px;">
                            <i class="fas fa-check me-1"></i>Enable
                        </button>
                        <button id="push-prompt-later" style="background:transparent;color:white;border:1px solid rgba(255,255,255,0.3);padding:8px 16px;border-radius:6px;cursor:pointer;font-size:13px;">
                            Later
                        </button>
                    </div>
                </div>
                <button id="push-prompt-close" style="background:none;border:none;color:white;opacity:0.7;cursor:pointer;padding:0;font-size:18px;line-height:1;">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        </div>
    `;
    document.body.appendChild(banner);
    
    document.getElementById('push-prompt-enable').addEventListener('click', async () => {
        banner.remove();
        const success = await PushNotifications.subscribe();
        if (success) {
            showPushSuccess();
        }
    });
    
    document.getElementById('push-prompt-later').addEventListener('click', () => {
        localStorage.setItem('pushPromptDismissed', Date.now().toString());
        banner.remove();
    });
    
    document.getElementById('push-prompt-close').addEventListener('click', () => {
        localStorage.setItem('pushPromptDismissed', Date.now().toString());
        banner.remove();
    });
}

function showPushSuccess() {
    const toast = document.createElement('div');
    toast.innerHTML = `
        <div style="position:fixed;bottom:20px;right:20px;background:#28a745;color:white;padding:12px 20px;border-radius:8px;box-shadow:0 4px 12px rgba(0,0,0,0.15);z-index:9999;font-family:inherit;">
            <i class="fas fa-check-circle me-2"></i>Push notifications enabled!
        </div>
    `;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}
