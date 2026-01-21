import os
import logging
from datetime import timedelta
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
    
    # Migration 7: Add LTI columns to courses table
    lti_course_columns = [
        ("lti_tool_id", "INTEGER REFERENCES lti_tools(id)"),
        ("lti_resource_link_id", "VARCHAR(200)"),
    ]
    for col_name, col_type in lti_course_columns:
        try:
            db.session.execute(text(f"ALTER TABLE courses ADD COLUMN {col_name} {col_type}"))
            db.session.commit()
            logging.info(f"Applied schema migration: courses.{col_name} added")
        except Exception as e:
            db.session.rollback()
            logging.debug(f"Schema migration skipped (likely already applied): {e}")
    
    # Migration 8: Add Facebook sync columns
    facebook_sync_columns = [
        ("users", "facebook_id", "VARCHAR(50) UNIQUE"),
        ("users", "google_id", "VARCHAR(50) UNIQUE"),
        ("users", "apple_id", "VARCHAR(100) UNIQUE"),
        ("users", "github_id", "VARCHAR(50) UNIQUE"),
        ("posts", "facebook_post_id", "VARCHAR(100) UNIQUE"),
    ]
    for table, col_name, col_type in facebook_sync_columns:
        try:
            db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}"))
            db.session.commit()
            logging.info(f"Applied schema migration: {table}.{col_name} added")
        except Exception as e:
            db.session.rollback()
            logging.debug(f"Schema migration skipped (likely already applied): {e}")
    
    # Migration 9: Add is_internal column to ad_advertisers
    try:
        db.session.execute(text("ALTER TABLE ad_advertisers ADD COLUMN is_internal BOOLEAN DEFAULT FALSE"))
        db.session.commit()
        logging.info("Applied schema migration: ad_advertisers.is_internal added")
    except Exception as e:
        db.session.rollback()
        logging.debug(f"Schema migration skipped (likely already applied): {e}")
    
    # Auto-create "Medicine and Money Show" as internal advertiser
    try:
        from models import AdAdvertiser
        existing = AdAdvertiser.query.filter_by(name='Medicine and Money Show').first()
        if not existing:
            advertiser = AdAdvertiser(
                name='Medicine and Money Show',
                category='finance',
                compliance_status='active',
                is_internal=True
            )
            db.session.add(advertiser)
            db.session.commit()
            logging.info("Created internal advertiser: Medicine and Money Show")
        elif not existing.is_internal:
            existing.is_internal = True
            db.session.commit()
            logging.info("Updated Medicine and Money Show to internal advertiser")
    except Exception as e:
        db.session.rollback()
        logging.debug(f"Internal advertiser creation skipped: {e}")
    
    # Auto-sync Ghost CMS articles on startup if database is empty
    try:
        from routes.opmed import auto_sync_ghost_articles
        auto_sync_ghost_articles()
    except Exception as e:
        logging.debug(f"Ghost auto-sync skipped: {e}")

from markupsafe import Markup

@app.template_filter('localtime')
def localtime_filter(dt, format='short'):
    """Output a datetime as a span with data-utc for client-side conversion"""
    if dt is None:
        return ''
    utc_str = dt.strftime('%Y-%m-%dT%H:%M:%S')
    fallback = dt.strftime('%b %d at %I:%M %p')
    return Markup(f'<span data-utc="{utc_str}" data-format="{format}">{fallback}</span>')

# Register render_content_with_links as a global template function
from utils.content import render_content_with_links
app.jinja_env.globals['render_content'] = render_content_with_links
