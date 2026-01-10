import os
import logging
from flask_login import LoginManager
from app import app, db

# Configure logging for production
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s'
)

# Set up Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

# Import models for user loader
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
from routes.errors import errors_bp

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
app.register_blueprint(errors_bp)

# Import legacy routes for backwards compatibility
import routes  # noqa: F401

# For deployment compatibility - Cloud Run and Gunicorn need this
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV") == "development"
    logging.info(f"Starting Flask app on 0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
