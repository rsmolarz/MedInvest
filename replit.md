# Overview

MedInvest is a social media platform designed for medical professionals to learn investment strategies and share financial knowledge. It combines social networking with investment education, enabling doctors to connect, share insights, and learn from peers. The platform facilitates discussions through posts, comments, and likes, and offers professional networking opportunities. Its business vision is to become the leading platform for medical professionals seeking to enhance their financial literacy and investment acumen, thereby addressing a significant market need for specialized financial education within the medical community.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Frontend Architecture
- **Template Engine**: Jinja2 with Bootstrap 5 for responsive UI.
- **UI Framework**: Bootstrap 5 with custom CSS for medical professional theming.
- **JavaScript**: Vanilla JavaScript for interactivity and validation.
- **Static Assets**: Flask's static file handling for CSS and JS.
- **Shared Package**: `medinvest-shared` (TypeScript) for common types, validators, API clients, constants, and utilities across web and mobile.

## Backend Architecture
- **Primary Application**: Flask web framework with SQLAlchemy ORM.
- **API Scaffold**: FastAPI for future investment deal management and financial integrations.
- **Database Layer**: SQLAlchemy with DeclarativeBase.
- **Authentication**: Flask-Login for session management (email/password), JWT-based token authentication for API (FastAPI).
- **Security**: Werkzeug for password hashing and session management, bcrypt for FastAPI.
- **Routing**: Flask blueprint pattern and FastAPI router-based organization.
- **Modular Design**: Migration to 13 modular blueprints for core features like authentication, main content, rooms, AMAs, deals, subscriptions, courses, events, mentorship, referral, portfolio, AI, and admin.
- **Social Media Features**: Posts, media attachments (images/videos), likes, comments, and following relationships.
- **Direct Messaging**: 1:1 secure conversations with inbox and thread views.
- **Comprehensive Platform Features**:
    - **Expert AMAs**: Scheduled Q&A sessions with financial experts, including registration and question submission.
    - **Investment Deal Marketplace**: Vetted investment opportunities (real estate, funds) with interest tracking.
    - **Mentorship Program**: Peer-to-peer guidance with session tracking.
    - **Courses & Events**: Educational content with enrollment and registration.
    - **Referral Program**: Unique codes and reward tiers.
    - **Premium Subscription**: Freemium model with tiered access.
- **Ad Serving System**: Internal system for serving targeted ads based on user profiles and content.
- **Operational & Moderation Infrastructure**:
    - **Verification Queue**: For managing user and content verification.
    - **Analytics API**: Admin endpoints for platform metrics (WAU, cohorts).
    - **Auto-Moderation**: Reputation-based posting, report thresholds, content hiding/locking.
    - **Content Reports**: User reporting system with admin resolution workflow.
    - **Activity Logging**: Centralized system for tracking user actions.
- **Enhanced Security**:
    - **Two-Factor Authentication (2FA)**: TOTP-based using pyotp and qrcode.
    - **Password Reset**: Secure token-based password reset flow.
- **LTI 1.3 Integration**: Single Sign-On for external learning platforms (e.g., Coursebox). Includes RSA key management, JWKS endpoint, OIDC flow, and admin interface for tool configuration.
- **Deployment**: Optimized health checks, port binding, and environment detection for cloud deployment.

## Data Models
- **User Management**: Professional verification, medical license tracking, role-based access control (User.is_admin).
- **Social Media System**: Posts (text, image, video, gallery), PostMedia, PostVote, Bookmark.
- **Engagement Fields**: referral_code, subscription_tier, points, level, login_streak.
- **Specialized Models**: ExpertAMA, AMAQuestion, AMARegistration, InvestmentDeal, DealInterest, Mentorship, MentorshipSession, Course, CourseModule, CourseEnrollment, Event, EventSession, EventRegistration, Referral, Subscription, Payment, EmailCampaign.
- **Ad Models**: AdAdvertiser, AdCampaign, AdCreative, AdImpression, AdClick.
- **Moderation Models**: verification_queue_entries, onboarding_prompts, user_prompt_dismissals, invite_credit_events, cohort_norms, moderation_events, content_reports, deal_outcomes, sponsor_profiles, sponsor_reviews.

## Database Design
- **Primary Database**: SQLite for development, PostgreSQL for production.
- **Connection Management**: Connection pooling with auto-reconnection.
- **Schema Management**: Automatic table creation on startup.
- **Data Relationships**: Foreign key relationships for interconnected data.

# External Dependencies

## Core Frameworks
- **Flask**: Primary web framework.
- **FastAPI**: Secondary API framework.
- **SQLAlchemy**: ORM.
- **Bootstrap 5**: Frontend CSS framework.

## Authentication & Security
- **Flask-Login**: User session management.
- **Werkzeug**: Password hashing, security utilities.
- **python-jose**: JWT token handling.
- **passlib**: Advanced password hashing (bcrypt).
- **pyotp**: TOTP for 2FA.
- **qrcode**: QR code generation for 2FA.
- **Social Login (OAuth 2.0)**: Google, Apple, Facebook, GitHub with dynamic redirect URI detection.

## Social Login Configuration
OAuth providers use dynamic redirect URI detection, automatically adapting to the current domain (development or production). Required environment variables:
- **Google**: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
- **Apple**: APPLE_CLIENT_ID (Service ID), APPLE_TEAM_ID, APPLE_KEY_ID, APPLE_PRIVATE_KEY (ES256 .p8 key)
- **Facebook**: FACEBOOK_APP_ID, FACEBOOK_APP_SECRET
- **GitHub**: GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET

After publishing, add the redirect URIs to each provider's developer console:
- Format: `https://your-domain/auth/{provider}/callback`
- Providers: google, apple, facebook, github

## Database Support
- **SQLite**: Default development database.
- **psycopg2-binary**: PostgreSQL adapter.

## Financial Service Integrations
- **Stripe**: Payment processing, subscriptions.
- **Plaid**: Bank account connectivity, financial data aggregation.
- **Persona**: Identity verification, KYC.

## Development & Deployment
- **Uvicorn**: ASGI server for FastAPI.
- **ProxyFix**: Werkzeug middleware for proxy header handling.
- **python-multipart**: File upload handling for FastAPI.
- **httpx**: Async HTTP client.

## Frontend Libraries
- **Font Awesome**: Icon library.

## Email Services
- **SendGrid/Postmark**: Abstraction via `mailer.py`.