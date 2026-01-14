import os
import logging
from flask import session
from app import app, db

# Configure logging for production
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s'
)

# Set up Replit Auth (includes Flask-Login)
from replit_auth import make_replit_blueprint, login_manager

# Configure login manager messages
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

# Make session permanent
@app.before_request
def make_session_permanent():
    session.permanent = True

# Register Replit Auth blueprint
app.register_blueprint(make_replit_blueprint(), url_prefix="/auth")

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
from routes.media import media_bp
from routes.notifications import notifications_bp
from routes.dm import dm_bp
from routes.news import news_bp
from routes.opmed import opmed_bp
from routes.connections import connections_bp
from routes.push import push_bp

app.register_blueprint(main_bp)
app.register_blueprint(auth_bp)

# Note: Google OAuth is now handled by custom routes in auth_bp
# The Flask-Dance blueprint was removed to avoid redirect_uri conflicts
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
app.register_blueprint(dm_bp)
app.register_blueprint(news_bp)
app.register_blueprint(opmed_bp)
app.register_blueprint(connections_bp)
app.register_blueprint(push_bp)
app.register_blueprint(errors_bp)

# Template filter for getting user by ID
from models import User
@app.template_filter('get_user')
def get_user_filter(user_id):
    return User.query.get(user_id)

# Import legacy routes for backwards compatibility
import routes  # noqa: F401

# For deployment compatibility - Cloud Run and Gunicorn need this
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV") == "development"
    logging.info(f"Starting Flask app on 0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
