import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging
logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "fallback-secret-for-development-only")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=2, x_host=2, x_for=2)

# Configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///medlearn.db")

# Configure database options
engine_options = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Deployment environment detection and optimization
if os.environ.get("REPLIT_DEPLOYMENT") or os.environ.get("GOOGLE_CLOUD_PROJECT"):
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

with app.app_context():
    # Import models to ensure tables are created
    import models  # noqa: F401
    db.create_all()
    logging.info("Database tables created")
    
    # Apply necessary schema migrations for existing databases
    try:
        from sqlalchemy import text
        # Fix medical_license constraint - should allow NULL for new registrations
        db.session.execute(text("ALTER TABLE users ALTER COLUMN medical_license DROP NOT NULL"))
        db.session.commit()
        logging.info("Applied schema migration: medical_license now nullable")
    except Exception as e:
        db.session.rollback()
        # Ignore if already nullable or table doesn't exist yet
        logging.debug(f"Schema migration skipped (likely already applied): {e}")
