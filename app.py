import os
import logging
from datetime import timedelta
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET",
                                "fallback-secret-for-development-only")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=2, x_host=2, x_for=2)

# Session lifetime settings - keep users logged in for 30 days
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=30)
app.config['REMEMBER_COOKIE_SECURE'] = True
app.config['REMEMBER_COOKIE_HTTPONLY'] = True
app.config['REMEMBER_COOKIE_SAMESITE'] = 'Lax'

# Session cookie settings for OAuth to work properly
app.config['SESSION_COOKIE_SECURE'] = True  # HTTPS only
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Allow OAuth redirects

# Facebook SDK configuration for templates
app.config['FACEBOOK_APP_ID'] = os.environ.get('FACEBOOK_APP_ID', '')

# Configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "sqlite:///medlearn.db")

# Configure database options
engine_options = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Deployment environment detection and optimization
if os.environ.get("REPLIT_DEPLOYMENT") or os.environ.get(
        "GOOGLE_CLOUD_PROJECT"):
    app.config["DEBUG"] = False
    app.config["TESTING"] = False
    # Optimize for deployment
    engine_options.update({
        "pool_size": 5,
        "max_overflow": 10,
        "pool_timeout": 30
    })

app.config["SQLALCHEMY_ENGINE_OPTIONS"] = engine_options
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize the app with the extension
db.init_app(app)

# Import models to register them with SQLAlchemy metadata
with app.app_context():
    import models  # noqa: F401
    
    # Verify and create any missing database tables on startup
    from utils.db_verify import verify_and_create_tables
    created = verify_and_create_tables(db, app)
    if created:
        logger.warning(f"Created missing database tables on startup: {created}")
