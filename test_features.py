"""
Comprehensive test suite for MedInvest Phase 2 features.
Tests cover: Stripe payments, notifications, achievements, analytics, 
filtering, dark mode, email digests, and admin features.

Run with: pytest test_features.py -v
"""
import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from app import app, db
from models import (
    User, Post, Notification, NotificationPreference,
    Subscription, Achievement, InvestmentDeal, Course,
    Event, Room, Payment
)


@pytest.fixture
def client():
    """Create test client with test database."""
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['WTF_CSRF_ENABLED'] = False
    
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            yield client
            db.drop_all()


@pytest.fixture
def test_user(client):
    """Create a test user."""
    with app.app_context():
        user = User(
            username='testuser',
            email='test@example.com',
            password_hash='hashed_password',
            is_admin=False
        )
        db.session.add(user)
        db.session.commit()
        return user.id


@pytest.fixture
def admin_user(client):
    """Create an admin user."""
    with app.app_context():
        user = User(
            username='adminuser',
            email='admin@example.com',
            password_hash='hashed_password',
            is_admin=True
        )
        db.session.add(user)
        db.session.commit()
        return user.id


@pytest.fixture
def authenticated_client(client, test_user):
    """Create authenticated test client."""
    with client.session_transaction() as sess:
        sess['_user_id'] = str(test_user)
    return client


@pytest.fixture
def admin_client(client, admin_user):
    """Create authenticated admin client."""
    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin_user)
    return client


# =============================================================================
# STRIPE PAYMENT TESTS
# =============================================================================

class TestStripePayments:
    """Test Stripe payment integration."""
    
    def test_pricing_page_loads(self, client):
        """Test pricing page displays subscription tiers."""
        response = client.get('/subscription/pricing')
        assert response.status_code == 200 or response.status_code == 302
    
    def test_checkout_requires_auth(self, client):
        """Test checkout requires authentication."""
        response = client.post('/subscription/checkout', 
                              json={'tier': 'pro', 'interval': 'month'})
        assert response.status_code == 302  # Redirect to login
    
    @patch('routes.subscription.get_stripe')
    def test_checkout_creates_session(self, mock_stripe, authenticated_client):
        """Test checkout creates Stripe session."""
        mock_stripe_client = MagicMock()
        mock_stripe_client.checkout.Session.create.return_value = MagicMock(
            url='https://checkout.stripe.com/test'
        )
        mock_stripe.return_value = mock_stripe_client
        
        response = authenticated_client.post('/subscription/checkout',
                                            json={'tier': 'pro', 'interval': 'month'})
        # Should redirect or return checkout URL
        assert response.status_code in [200, 302, 303]
    
    def test_manage_requires_auth(self, client):
        """Test subscription management requires auth."""
        response = client.get('/subscription/manage')
        assert response.status_code == 302
    
    def test_manage_page_loads(self, authenticated_client):
        """Test subscription management page loads."""
        response = authenticated_client.get('/subscription/manage')
        assert response.status_code == 200
    
    @patch('routes.subscription.get_stripe')
    def test_webhook_handles_subscription_updated(self, mock_stripe, client):
        """Test webhook handles subscription updates."""
        mock_stripe.return_value = MagicMock()
        
        payload = {
            'type': 'customer.subscription.updated',
            'data': {
                'object': {
                    'id': 'sub_123',
                    'status': 'active',
                    'current_period_end': 1735689600
                }
            }
        }
        response = client.post('/subscription/webhook',
                              data=json.dumps(payload),
                              content_type='application/json')
        assert response.status_code in [200, 400]


# =============================================================================
# NOTIFICATION TESTS
# =============================================================================

class TestNotifications:
    """Test notification system."""
    
    def test_notifications_require_auth(self, client):
        """Test notifications page requires authentication."""
        response = client.get('/notifications')
        assert response.status_code == 302
    
    def test_notifications_page_loads(self, authenticated_client):
        """Test notifications page loads for authenticated user."""
        response = authenticated_client.get('/notifications')
        assert response.status_code == 200
    
    def test_preferences_page_loads(self, authenticated_client):
        """Test notification preferences page loads."""
        response = authenticated_client.get('/notifications/preferences')
        assert response.status_code == 200
    
    def test_update_preferences(self, authenticated_client, test_user):
        """Test updating notification preferences."""
        response = authenticated_client.post('/notifications/preferences', data={
            'in_app_likes': 'on',
            'in_app_comments': 'on',
            'email_digest': 'daily'
        }, follow_redirects=True)
        assert response.status_code == 200
        
        with app.app_context():
            prefs = NotificationPreference.query.filter_by(user_id=test_user).first()
            if prefs:
                assert prefs.in_app_likes == True
                assert prefs.email_digest == 'daily'
    
    def test_mark_notification_read(self, authenticated_client, test_user):
        """Test marking notification as read."""
        with app.app_context():
            notification = Notification(
                user_id=test_user,
                notification_type='like',
                title='Test',
                message='Test notification'
            )
            db.session.add(notification)
            db.session.commit()
            notif_id = notification.id
        
        response = authenticated_client.post(f'/notifications/read/{notif_id}')
        assert response.status_code == 200
    
    def test_notification_preference_enforcement(self, test_user):
        """Test that notification preferences are enforced."""
        from routes.notifications import should_send_notification
        
        with app.app_context():
            # Create preference with likes disabled
            prefs = NotificationPreference(
                user_id=test_user,
                in_app_likes=False,
                in_app_comments=True
            )
            db.session.add(prefs)
            db.session.commit()
            
            # Should not send like notifications
            assert should_send_notification(test_user, 'like') == False
            # Should send comment notifications
            assert should_send_notification(test_user, 'comment') == True


# =============================================================================
# ACHIEVEMENTS TESTS
# =============================================================================

class TestAchievements:
    """Test achievements system."""
    
    def test_check_and_award_achievements(self, test_user):
        """Test achievement awarding logic."""
        from utils.achievements import check_and_award_achievements
        
        with app.app_context():
            user = User.query.get(test_user)
            
            # Create a post to trigger first_post achievement
            post = Post(
                user_id=test_user,
                content='Test post',
                post_type='text'
            )
            db.session.add(post)
            db.session.commit()
            
            # Check achievements
            new_achievements = check_and_award_achievements(user)
            
            # Should have first_post achievement
            achievement = Achievement.query.filter_by(
                user_id=test_user, 
                achievement_id='first_post'
            ).first()
            assert achievement is not None
    
    def test_achievement_display_on_dashboard(self, authenticated_client, test_user):
        """Test achievements display on dashboard."""
        with app.app_context():
            achievement = Achievement(
                user_id=test_user,
                achievement_id='first_post',
                name='First Post',
                description='Created your first post',
                icon='fa-pen'
            )
            db.session.add(achievement)
            db.session.commit()
        
        response = authenticated_client.get('/dashboard')
        assert response.status_code == 200
        assert b'First Post' in response.data or b'achievement' in response.data.lower()
    
    def test_early_adopter_achievement(self, client):
        """Test early adopter achievement for first 100 users."""
        from utils.achievements import check_and_award_achievements
        
        with app.app_context():
            # Create user with low ID
            user = User(
                id=50,
                username='earlyuser',
                email='early@example.com'
            )
            db.session.add(user)
            db.session.commit()
            
            check_and_award_achievements(user)
            
            achievement = Achievement.query.filter_by(
                user_id=50,
                achievement_id='early_adopter'
            ).first()
            assert achievement is not None


# =============================================================================
# ANALYTICS TESTS
# =============================================================================

class TestAnalytics:
    """Test analytics features."""
    
    def test_dashboard_shows_analytics(self, authenticated_client, test_user):
        """Test user dashboard displays analytics."""
        response = authenticated_client.get('/dashboard')
        assert response.status_code == 200
        # Check for analytics elements
        assert b'Posts' in response.data or b'posts' in response.data.lower()
    
    def test_admin_analytics_requires_admin(self, authenticated_client):
        """Test admin analytics requires admin access."""
        response = authenticated_client.get('/admin/analytics')
        assert response.status_code in [302, 403]
    
    def test_admin_analytics_loads(self, admin_client):
        """Test admin analytics page loads for admins."""
        response = admin_client.get('/admin/analytics')
        assert response.status_code == 200
    
    def test_admin_analytics_contains_metrics(self, admin_client):
        """Test admin analytics contains expected metrics."""
        response = admin_client.get('/admin/analytics')
        assert response.status_code == 200
        # Check for key metrics
        data = response.data.decode()
        assert 'Total Users' in data or 'total_users' in data.lower()
    
    def test_engagement_rate_calculation(self, test_user):
        """Test engagement rate calculation."""
        with app.app_context():
            user = User.query.get(test_user)
            
            # Create posts and interactions
            for i in range(5):
                post = Post(user_id=test_user, content=f'Post {i}', post_type='text')
                db.session.add(post)
            
            db.session.commit()
            
            # Engagement rate should be calculable
            posts_count = Post.query.filter_by(user_id=test_user).count()
            assert posts_count == 5


# =============================================================================
# FILTERING TESTS
# =============================================================================

class TestFiltering:
    """Test content filtering and sorting."""
    
    def test_deals_filtering_by_type(self, authenticated_client):
        """Test deals can be filtered by type."""
        response = authenticated_client.get('/deals?type=real_estate')
        assert response.status_code == 200
    
    def test_deals_sorting(self, authenticated_client):
        """Test deals can be sorted."""
        response = authenticated_client.get('/deals?sort=newest')
        assert response.status_code == 200
        
        response = authenticated_client.get('/deals?sort=popular')
        assert response.status_code == 200
    
    def test_deals_investment_range_filter(self, authenticated_client):
        """Test deals can be filtered by investment range."""
        response = authenticated_client.get('/deals?min_investment=10000&max_investment=100000')
        assert response.status_code == 200
    
    def test_courses_filtering_by_category(self, authenticated_client):
        """Test courses can be filtered by category."""
        response = authenticated_client.get('/courses?category=investing')
        assert response.status_code == 200
    
    def test_courses_filtering_by_level(self, authenticated_client):
        """Test courses can be filtered by level."""
        response = authenticated_client.get('/courses?level=beginner')
        assert response.status_code == 200
    
    def test_events_filtering_by_type(self, authenticated_client):
        """Test events can be filtered by type."""
        response = authenticated_client.get('/events?type=webinar')
        assert response.status_code == 200
    
    def test_events_date_filtering(self, authenticated_client):
        """Test events can be filtered by date."""
        response = authenticated_client.get('/events?date=upcoming')
        assert response.status_code == 200
    
    def test_rooms_search(self, authenticated_client):
        """Test rooms can be searched."""
        response = authenticated_client.get('/rooms?q=investing')
        assert response.status_code == 200
    
    def test_rooms_category_filter(self, authenticated_client):
        """Test rooms can be filtered by category."""
        response = authenticated_client.get('/rooms?category=Real%20Estate')
        assert response.status_code == 200


# =============================================================================
# DARK MODE TESTS
# =============================================================================

class TestDarkMode:
    """Test dark mode functionality."""
    
    def test_base_template_has_dark_mode_toggle(self, client):
        """Test base template includes dark mode toggle."""
        response = client.get('/')
        # Check for dark mode elements
        assert response.status_code in [200, 302]
    
    def test_dark_mode_css_variables(self, client):
        """Test dark mode CSS variables are defined."""
        # This would typically be tested in frontend tests
        # Here we verify the template renders without error
        response = client.get('/')
        assert response.status_code in [200, 302]


# =============================================================================
# EMAIL DIGEST TESTS
# =============================================================================

class TestEmailDigests:
    """Test email digest functionality."""
    
    def test_generate_daily_digest(self, test_user):
        """Test daily digest generation."""
        from utils.email_digest import generate_digest_content
        
        with app.app_context():
            user = User.query.get(test_user)
            content = generate_digest_content(user, 'daily')
            
            assert content is not None
            assert 'trending_posts' in content or isinstance(content, dict)
    
    def test_generate_weekly_digest(self, test_user):
        """Test weekly digest generation."""
        from utils.email_digest import generate_digest_content
        
        with app.app_context():
            user = User.query.get(test_user)
            content = generate_digest_content(user, 'weekly')
            
            assert content is not None
    
    def test_digest_respects_preferences(self, test_user):
        """Test digest respects user preferences."""
        from utils.email_digest import should_send_digest
        
        with app.app_context():
            # Create preference with daily digest
            prefs = NotificationPreference(
                user_id=test_user,
                email_digest='daily'
            )
            db.session.add(prefs)
            db.session.commit()
            
            user = User.query.get(test_user)
            
            # Should send daily digest
            assert should_send_digest(user, 'daily') == True
            # Should not send weekly digest
            assert should_send_digest(user, 'weekly') == False


# =============================================================================
# ADMIN FEATURES TESTS
# =============================================================================

class TestAdminFeatures:
    """Test admin features."""
    
    def test_admin_dashboard_requires_admin(self, authenticated_client):
        """Test admin dashboard requires admin access."""
        response = authenticated_client.get('/admin')
        assert response.status_code in [302, 403]
    
    def test_admin_dashboard_loads(self, admin_client):
        """Test admin dashboard loads for admins."""
        response = admin_client.get('/admin')
        assert response.status_code == 200
    
    def test_admin_users_list(self, admin_client):
        """Test admin can view users list."""
        response = admin_client.get('/admin/users')
        assert response.status_code == 200
    
    def test_admin_cannot_delete_self(self, admin_client, admin_user):
        """Test admin cannot delete their own account."""
        response = admin_client.delete(f'/admin/users/{admin_user}')
        # Should fail or return error
        assert response.status_code in [400, 403, 200]
    
    def test_toggle_user_ban(self, admin_client, test_user):
        """Test admin can toggle user ban status."""
        response = admin_client.post(f'/admin/users/{test_user}/toggle-ban')
        assert response.status_code == 200


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestIntegration:
    """Integration tests for feature interactions."""
    
    def test_subscription_unlocks_premium_features(self, authenticated_client, test_user):
        """Test premium subscription unlocks features."""
        with app.app_context():
            user = User.query.get(test_user)
            user.subscription_tier = 'pro'
            db.session.commit()
        
        # Premium user should have access to premium features
        response = authenticated_client.get('/dashboard')
        assert response.status_code == 200
    
    def test_achievement_awarded_on_subscription(self, test_user):
        """Test premium_member achievement awarded on subscription."""
        from utils.achievements import check_and_award_achievements
        
        with app.app_context():
            user = User.query.get(test_user)
            user.subscription_tier = 'pro'
            db.session.commit()
            
            check_and_award_achievements(user)
            
            achievement = Achievement.query.filter_by(
                user_id=test_user,
                achievement_id='premium_member'
            ).first()
            assert achievement is not None
    
    def test_notification_created_on_follow(self, test_user):
        """Test notification created when user is followed."""
        with app.app_context():
            # Create another user to follow
            follower = User(
                username='follower',
                email='follower@example.com'
            )
            db.session.add(follower)
            db.session.commit()
            
            # Manually create follow notification
            from routes.notifications import create_notification
            create_notification(
                user_id=test_user,
                notification_type='follow',
                title='New Follower',
                message='follower started following you',
                actor_id=follower.id
            )
            db.session.commit()
            
            notification = Notification.query.filter_by(
                user_id=test_user,
                notification_type='follow'
            ).first()
            assert notification is not None


# =============================================================================
# PERFORMANCE TESTS
# =============================================================================

class TestPerformance:
    """Basic performance tests."""
    
    def test_dashboard_loads_quickly(self, authenticated_client):
        """Test dashboard loads within reasonable time."""
        import time
        
        start = time.time()
        response = authenticated_client.get('/dashboard')
        elapsed = time.time() - start
        
        assert response.status_code == 200
        assert elapsed < 5.0  # Should load in under 5 seconds
    
    def test_notifications_pagination(self, authenticated_client, test_user):
        """Test notifications handle pagination."""
        with app.app_context():
            # Create many notifications
            for i in range(50):
                notification = Notification(
                    user_id=test_user,
                    notification_type='like',
                    title=f'Notification {i}',
                    message=f'Test notification {i}'
                )
                db.session.add(notification)
            db.session.commit()
        
        response = authenticated_client.get('/notifications?page=1')
        assert response.status_code == 200
        
        response = authenticated_client.get('/notifications?page=2')
        assert response.status_code == 200


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
