"""
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
