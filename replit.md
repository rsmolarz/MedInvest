# Overview

MedLearn Invest is a comprehensive educational platform designed specifically for medical professionals to learn investment strategies and financial management. The application combines structured learning modules, community forums, portfolio simulation, and professional verification to create a tailored investment education experience for doctors and healthcare professionals.

The platform features two main architectures: a primary Flask-based web application for the educational content and user interface, and a FastAPI scaffold for potential future investment deal management and financial integrations.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Frontend Architecture
- **Template Engine**: Jinja2 templates with Bootstrap 5 for responsive design
- **UI Framework**: Bootstrap 5 with custom CSS for medical professional theming
- **JavaScript**: Vanilla JavaScript for enhanced interactivity, form validation, and Bootstrap component initialization
- **Static Assets**: Organized CSS and JavaScript files served through Flask's static file handling

## Backend Architecture
- **Primary Application**: Flask web framework with SQLAlchemy ORM
- **Database Layer**: SQLAlchemy with DeclarativeBase for modern ORM patterns
- **Authentication**: Flask-Login for session management with email/password authentication
- **Security**: Werkzeug password hashing and session management
- **Routing**: Flask blueprint pattern for organized route handling

## Data Models
- **User Management**: Professional verification system with medical license tracking
- **Learning System**: Modular content delivery with progress tracking
- **Community Features**: Forum topics and posts with categorization
- **Portfolio Simulation**: Virtual transaction tracking for investment practice
- **Resource Management**: Educational materials and documentation

## Database Design
- **Primary Database**: SQLite for development with PostgreSQL support via environment configuration
- **Connection Management**: Connection pooling with automatic reconnection handling
- **Schema Management**: Automatic table creation on application startup
- **Data Relationships**: Foreign key relationships between users, modules, progress, and forum content

## Authentication & Authorization
- **User Sessions**: Flask-Login for secure session management
- **Professional Verification**: Medical license number validation and verification status tracking
- **Access Control**: Login-required decorators for protected routes
- **Password Security**: Werkzeug secure password hashing

## FastAPI Scaffold Architecture
- **API Framework**: FastAPI with automatic OpenAPI documentation
- **Authentication**: JWT-based token authentication with OAuth2 password bearer
- **Database Integration**: SQLAlchemy async support with dependency injection
- **Security**: bcrypt password hashing and JWT token management
- **Modular Design**: Router-based organization for scalable API development

# External Dependencies

## Core Frameworks
- **Flask**: Primary web framework for application routing and templating
- **FastAPI**: Secondary API framework for financial service integrations
- **SQLAlchemy**: ORM for database operations and model definitions
- **Bootstrap 5**: Frontend CSS framework for responsive design
- **Font Awesome**: Icon library for UI enhancement

## Authentication & Security
- **Flask-Login**: User session management and authentication
- **Werkzeug**: Password hashing and security utilities
- **python-jose**: JWT token handling for API authentication
- **passlib**: Advanced password hashing with bcrypt support

## Database Support
- **SQLite**: Default development database
- **psycopg2-binary**: PostgreSQL adapter for production deployments
- **Database URL Configuration**: Environment-based database connection management

## Financial Service Integrations
- **Stripe**: Payment processing and subscription management capabilities
- **Plaid**: Bank account connectivity and financial data aggregation
- **Persona**: Identity verification and KYC compliance services

## Development & Deployment
- **Uvicorn**: ASGI server for FastAPI applications
- **ProxyFix**: Werkzeug middleware for proper header handling behind proxies
- **python-multipart**: File upload handling for FastAPI
- **httpx**: Async HTTP client for external API communications

## Frontend Libraries
- **Bootstrap CSS/JS**: Responsive design components and utilities
- **Font Awesome**: Professional icon set for medical and financial themes
- **Custom Styling**: Medical professional color scheme and theming