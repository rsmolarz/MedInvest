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

# Session cookie settings for OAuth to work properly
app.config['SESSION_COOKIE_SECURE'] = True  # HTTPS only
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Allow OAuth redirects

# Facebook SDK configuration for templates
app.config['FACEBOOK_APP_ID'] = os.environ.get('FACEBOOK_APP_ID', '')

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
    from sqlalchemy import text
    
    # Migration 1: Fix medical_license constraint
    try:
        db.session.execute(text("ALTER TABLE users ALTER COLUMN medical_license DROP NOT NULL"))
        db.session.commit()
        logging.info("Applied schema migration: medical_license now nullable")
    except Exception as e:
        db.session.rollback()
        logging.debug(f"Schema migration skipped (likely already applied): {e}")
    
    # Migration 2: Add is_anonymous column to comments table
    try:
        db.session.execute(text("ALTER TABLE comments ADD COLUMN is_anonymous BOOLEAN DEFAULT FALSE"))
        db.session.commit()
        logging.info("Applied schema migration: comments.is_anonymous added")
    except Exception as e:
        db.session.rollback()
        logging.debug(f"Schema migration skipped (likely already applied): {e}")
    
    # Migration 2b: Add npi_verified column to users table
    try:
        db.session.execute(text("ALTER TABLE users ADD COLUMN npi_verified BOOLEAN DEFAULT FALSE"))
        db.session.commit()
        logging.info("Applied schema migration: users.npi_verified added")
    except Exception as e:
        db.session.rollback()
        logging.debug(f"Schema migration skipped (likely already applied): {e}")
    
    # Migration 3: Add ghost_id column to opmed_articles table for Ghost CMS sync
    try:
        db.session.execute(text("ALTER TABLE opmed_articles ADD COLUMN ghost_id VARCHAR(100) UNIQUE"))
        db.session.commit()
        logging.info("Applied schema migration: opmed_articles.ghost_id added")
    except Exception as e:
        db.session.rollback()
        logging.debug(f"Schema migration skipped (likely already applied): {e}")
    
    # Migration 4: Add editorial workflow columns to opmed_articles
    editorial_columns = [
        ("submitted_at", "TIMESTAMP"),
        ("reviewed_by_id", "INTEGER REFERENCES users(id)"),
        ("reviewed_at", "TIMESTAMP"),
        ("editor_notes", "TEXT"),
        ("revision_count", "INTEGER DEFAULT 0"),
        ("word_count", "INTEGER DEFAULT 0"),
        ("reading_time_minutes", "INTEGER DEFAULT 0"),
        ("meta_description", "VARCHAR(300)"),
        ("meta_keywords", "VARCHAR(200)"),
        ("share_count", "INTEGER DEFAULT 0"),
    ]
    for col_name, col_type in editorial_columns:
        try:
            db.session.execute(text(f"ALTER TABLE opmed_articles ADD COLUMN {col_name} {col_type}"))
            db.session.commit()
            logging.info(f"Applied schema migration: opmed_articles.{col_name} added")
        except Exception as e:
            db.session.rollback()
            logging.debug(f"Schema migration skipped (likely already applied): {e}")
    
    # Migration 5: Add course_url column to courses table
    try:
        db.session.execute(text("ALTER TABLE courses ADD COLUMN course_url VARCHAR(500)"))
        db.session.commit()
        logging.info("Applied schema migration: courses.course_url added")
    except Exception as e:
        db.session.rollback()
        logging.debug(f"Schema migration skipped (likely already applied): {e}")
    
    # Migration 6: Add course_embed_code column to courses table
    try:
        db.session.execute(text("ALTER TABLE courses ADD COLUMN course_embed_code TEXT"))
        db.session.commit()
        logging.info("Applied schema migration: courses.course_embed_code added")
    except Exception as e:
        db.session.rollback()
        logging.debug(f"Schema migration skipped (likely already applied): {e}")
    
    # Auto-sync Ghost CMS articles on startup if database is empty
    try:
        from routes.opmed import auto_sync_ghost_articles
        auto_sync_ghost_articles()
    except Exception as e:
        logging.debug(f"Ghost auto-sync skipped: {e}")
