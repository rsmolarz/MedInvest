#!/usr/bin/env python3
"""
Alternative entry point for Replit deployment
This file ensures compatibility with different deployment methods
"""
import os
import logging
from app import app

# Configure logging
logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logging.info(f"Starting MedInvest app on 0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)