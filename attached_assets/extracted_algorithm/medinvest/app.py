cat app.py
  qpython3 << 'EOF'
# Create comprehensive test suite for Phase 2
test_code = '''import pytest
import json
from datetime import datetime, timedelta
from flask import Flask
from models import db, User, SubscriptionTier, Deal, Course, AMA, Notification
from routes.auth import auth_bp
from routes.subscription import subscription_bp
from routes.deals import deals_bp
from routes.courses import courses_bp
from routes.ama import ama_bp
from routes.admin import admin_bp


@pytest.fixture
def app():
    """Create and configure a test app instance"""
        app = Flask(__name__)
            app.config['''TESTING'] = True
                app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    
    db.init_app(app)
    app.register_blueprint(auth_bp)
    app.register_blueprint(subscription_bp)
    app.register_blueprint(deals_bp)
    app.register_blueprint(courses_bp)
    app.register_blueprint(ama_bp)
    app.register_blueprint(admin_bp)
    
    with app.app_context():
                db.create_all()
                yield app
                db.session.remove()
                db.drop_all()
        

@pytest.fixture
def client(app):
        """""Create a test client"""
        return app.test_client()
    

class TestAuthentication:
        """Test authentication routes"""
        
        def test_signup_success(self, client):
                    response = client.post('/auth/signup', json={
                                    'username': 'testuser',
                                    'email': 'test@example.com',
                                    'password': 'password123',
                                    'specialty': 'Cardiology'
                    })
                    assert response.status_code in [200, 201, 302]
                
        def test_login_success(self, client, app):
                    with app.app_context():
                                    user = User(username='testuser', email='test@example.com', specialty='Cardiology')
                                    user.set_password('password123')
                                    db.session.add(user)
                                    db.session.commit()
                                
                    response = client.post('/auth/login', json={
                                    'email': 'test@example.com',
                                    'password': 'password123'
                    })
                    assert response.status_code in [200, 302]
                
        def test_login_invalid_password(self, client, app):
                    with app.app_context():
                                    user = User(username='testuser', email='test@example.com', specialty='Cardiology')
                                    user.set_password('password123')
                                    db.session.add(user)
                                    db.session.commit()
                                
                    response = client.post('/auth/login', json={
                                    'email': 'test@example.com',
                                    'password': 'wrongpassword'
                    })
                    assert response.status_code != 200
            
    
class TestSubscription:
        """Test subscription management"""
        
        def test_get_subscription_tiers(self, client):
                    response = client.get('/subscription/tiers')
                    assert response.status_code == 200
                
        def test_create_subscription(self, client, app):
                    with app.app_context():
                                    user = User(username='testuser', email='test@example.com', specialty='Cardiology')
                                    db.session.add(user)
                                    db.session.commit()
                                    user_id = user.id
                                
                    response = client.post('/subscription/subscribe', json={
                                    'user_id': user_id,
                                    'tier': 'premium',
                                    'payment_method': 'stripe'
                    })
                    assert response.status_code in [200, 201, 302]
            
    
class TestDeals:
        """Test investment deals"""
        
        def test_get_deals(self, client):
                    response = client.get('/deals')
                    assert response.status_code == 200
                
        def test_create_deal(self, client, app):
                    with app.app_context():
                                    user = User(username='creator', email='creator@example.com', specialty='Finance')
                                    db.session.add(user)
                                    db.session.commit()
                                    user_id = user.id
                                
                    response = client.post('/deals/create', json={
                                    'title': 'Test Deal',
                                    'description': 'A test investment opportunity',
                                    'target_amount': 100000,
                                    'min_investment': 5000,
                                    'creator_id': user_id
                    })
                    assert response.status_code in [200, 201, 302]
            
    
class TestCourses:
        """Test educational courses"""
        
        def test_get_courses(self, client):
                    response = client.get('/courses')
                    assert response.status_code == 200
                
        def test_create_course(self, client, app):
                    with app.app_context():
                                    instructor = User(username='instructor', email='instructor@example.com', specialty='Education')
                                    db.session.add(instructor)
                                    db.session.commit()
                                    instructor_id = instructor.id
                                
                    response = client.post('/courses/create', json={
                                    'title': 'Investment 101',
                                    'description': 'Learn investment basics',
                                    'instructor_id': instructor_id,
                                    'price': 99.99
                    })
                    assert response.status_code in [200, 201, 302]
            
    
class TestAMA:
        """Test Ask Me Anything sessions"""
        
        def test_get_amas(self, client):
                    response = client.get('/ama')
                    assert response.status_code == 200
                
        def test_create_ama(self, client, app):
                    with app.app_context():
                                    expert = User(username='expert', email='expert@example.com', specialty='Medicine')
                                    db.session.add(expert)
                                    db.session.commit()
                                    expert_id = expert.id
                                
                    response = client.post('/ama/create', json={
                                    'title': 'Health Investment Strategy',
                                    'description': 'Expert advice on health sector investments',
                                    'expert_id': expert_id,
                                    'scheduled_time': (datetime.utcnow() + timedelta(days=1)).isoformat()
                    })
                    assert response.status_code in [200, 201, 302]
            
    
class TestNotifications:
        """Test notification system"""
        
        def test_send_notification(self, client, app):
                    with app.app_context():
                                    user = User(username='testuser', email='test@example.com', specialty='Cardiology')
                                    db.session.add(user)
                                    db.session.commit()
                                    user_id = user.id
                                
                    response = client.post('/notifications/send', json={
                                    'user_id': user_id,
                                    'title': 'Test Notification',
                                    'message': 'This is a test notification',
                                    'type': 'deal_update'
                    })
                    assert response.status_code in [200, 201]
            
    
class TestAnalytics:
        """Test analytics endpoints"""
        
        def test_get_user_analytics(self, client, app):
                    with app.app_context():
                                    user = User(username='testuser', email='test@example.com', specialty='Cardiology')
                                    db.session.add(user)
                                    db.session.commit()
                                    user_id = user.id
                                
                    response = client.get(f'/analytics/user/{user_id}')
                    assert response.status_code == 200
                
        def test_get_platform_analytics(self, client):
                    response = client.get('/analytics/platform')
                    assert response.status_code == 200
            
    
class TestAdminPanel:
        """Test admin functionality"""
        
        def test_admin_dashboard(self, client):
                    response = client.get('/admin/dashboard')
                    assert response.status_code in [200, 302]  # 302 if login required
            
    
if __name__ == '__main__':
        pytest.main([__file__, '-v', '--tb=short'])
    '''
    
    with open('''tests/test_suite.py', 'w') as f:
    f.write(test_code)

print("✓ Test suite created: tests/test_suite.py")
EOF

"
MedInvest - Investment Community for Physicians
Main Application File
"""
import os
from flask import Flask
from flask_login import LoginManager

# Import db from models to avoid circular import
from models import db
login_manager = LoginManager()


def create_app():
    """Application factory"""
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///medinvest.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize extensions with app
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    
    # User loader
    from models import User
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Register blueprints
    from routes.main import main_bp
    from routes.auth import auth_bp
    from routes.rooms import rooms_bp
    from routes.ama import ama_bp
    from routes.deals import deals_bp
    from routes.subscription import subscription_bp
    from routes.courses import courses_bp
    from routes.events import events_bp
    from routes.mentorship import mentorship_bp
    from routes.referral import referral_bp
    from routes.portfolio import portfolio_bp
    from routes.ai import ai_bp
    from routes.admin import admin_bp
    from routes.media import media_bp
    from routes.notifications import notifications_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(rooms_bp)
    app.register_blueprint(ama_bp)
    app.register_blueprint(deals_bp)
    app.register_blueprint(subscription_bp)
    app.register_blueprint(courses_bp)
    app.register_blueprint(events_bp)
    app.register_blueprint(mentorship_bp)
    app.register_blueprint(referral_bp)
    app.register_blueprint(portfolio_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(media_bp)
    app.register_blueprint(notifications_bp)
    
    # Error handlers
    from routes.errors import errors_bp
    app.register_blueprint(errors_bp)
    
    # Create database tables
    with app.app_context():
        db.create_all()
    
    return app


# Create app instance
app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
