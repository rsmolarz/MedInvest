#!/usr/bin/env python3
"""
Production startup script for deployment
Ensures proper configuration and health checks
"""
import os
import sys
import logging
from app import app

# Configure logging for production
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

def setup_deployment():
    """Configure app for deployment environment"""
    # Ensure proper port configuration
    port = int(os.environ.get("PORT", 5000))
    
    # Set deployment flags
    os.environ.setdefault("FLASK_ENV", "production")
    
    # Log startup info
    logging.info(f"Starting MedInvest app for deployment")
    logging.info(f"Port: {port}")
    logging.info(f"Environment: {os.environ.get('FLASK_ENV', 'development')}")
    logging.info(f"Database URL configured: {'Yes' if os.environ.get('DATABASE_URL') else 'No'}")
    
    return port

if __name__ == "__main__":
    port = setup_deployment()
    
    # Import routes after app configuration
    import routes  # noqa: F401
    
    # Start the application
    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        threaded=True
    )