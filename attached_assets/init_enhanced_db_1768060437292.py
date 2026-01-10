"""
Database Initialization Script for Enhanced MedInvest Features
Creates tables and populates sample data for:
- Investment Rooms
- Achievements
- Trending Topics
"""
from app import app, db
from models_enhanced import (
    InvestmentRoom, RoomMembership, Achievement, TrendingTopic,
    User, Post
)
import logging

logging.basicConfig(level=logging.INFO)


def create_investment_rooms():
    """Create specialty and topic-based investment rooms"""
    rooms_data = [
        # Specialty Rooms
        {
            'name': 'Cardiology Investment Club',
            'description': 'Investment strategies and financial planning for cardiologists',
            'room_type': 'specialty',
            'specialty': 'Cardiology',
            'icon': 'fas fa-heartbeat',
            'is_public': True
        },
        {
            'name': 'Anesthesiology Finance',
            'description': 'Maximizing income and building wealth as an anesthesiologist',
            'room_type': 'specialty',
            'specialty': 'Anesthesiology',
            'icon': 'fas fa-procedures',
            'is_public': True
        },
        {
            'name': 'Surgery Practice Owners',
            'description': 'Practice ownership, partnerships, and investment opportunities',
            'room_type': 'specialty',
            'specialty': 'Surgery',
            'icon': 'fas fa-user-md',
            'is_public': True
        },
        {
            'name': 'Primary Care Investors',
            'description': 'Building wealth on a primary care physician salary',
            'room_type': 'specialty',
            'specialty': 'Family Medicine',
            'icon': 'fas fa-clinic-medical',
            'is_public': True
        },
        
        # Career Stage Rooms
        {
            'name': 'Residents & Fellows: Starting from Zero',
            'description': 'Investment strategies for physicians in training',
            'room_type': 'career_stage',
            'icon': 'fas fa-graduation-cap',
            'is_public': True
        },
        {
            'name': 'First 5 Years Post-Residency',
            'description': 'Managing student loans while building wealth',
            'room_type': 'career_stage',
            'icon': 'fas fa-rocket',
            'is_public': True
        },
        {
            'name': 'Mid-Career Wealth Building',
            'description': 'Aggressive growth strategies for established physicians',
            'room_type': 'career_stage',
            'icon': 'fas fa-chart-line',
            'is_public': True
        },
        {
            'name': 'FIRE: Financial Independence',
            'description': 'Early retirement strategies for physicians',
            'room_type': 'career_stage',
            'icon': 'fas fa-fire',
            'is_public': True
        },
        
        # Topic Rooms
        {
            'name': 'Medical Real Estate Investors',
            'description': 'MOBs, surgery centers, and rental properties',
            'room_type': 'topic',
            'icon': 'fas fa-building',
            'is_public': True
        },
        {
            'name': 'Healthcare Stock Analysis',
            'description': 'Leveraging your medical expertise in stock investing',
            'room_type': 'topic',
            'icon': 'fas fa-chart-bar',
            'is_public': True
        },
        {
            'name': 'Tax Optimization for High Earners',
            'description': 'Strategies to minimize tax burden legally',
            'room_type': 'topic',
            'icon': 'fas fa-calculator',
            'is_public': True
        },
        {
            'name': 'Index Fund & Passive Investing',
            'description': 'Set it and forget it wealth building',
            'room_type': 'topic',
            'icon': 'fas fa-chart-pie',
            'is_public': True
        },
        {
            'name': 'Side Hustles for Physicians',
            'description': 'Generate additional income streams',
            'room_type': 'topic',
            'icon': 'fas fa-briefcase',
            'is_public': True
        },
        {
            'name': 'Student Loan Payoff Strategies',
            'description': 'PSLF, refinancing, and aggressive paydown methods',
            'room_type': 'topic',
            'icon': 'fas fa-hand-holding-usd',
            'is_public': True
        },
    ]
    
    created_count = 0
    for room_data in rooms_data:
        existing = InvestmentRoom.query.filter_by(name=room_data['name']).first()
        if not existing:
            room = InvestmentRoom(**room_data)
            db.session.add(room)
            created_count += 1
    
    db.session.commit()
    logging.info(f"Created {created_count} investment rooms")


def create_achievements():
    """Create achievement badges"""
    achievements_data = [
        # Learning Achievements
        {
            'name': 'First Step',
            'description': 'Complete your first learning module',
            'icon': '🎓',
            'category': 'learning',
            'points': 10,
            'requirements': '{"modules_completed": 1}'
        },
        {
            'name': 'Investment Scholar',
            'description': 'Complete 10 learning modules',
            'icon': '📚',
            'category': 'learning',
            'points': 100,
            'requirements': '{"modules_completed": 10}'
        },
        {
            'name': 'Master Investor',
            'description': 'Complete all learning modules',
            'icon': '🏆',
            'category': 'learning',
            'points': 500,
            'requirements': '{"modules_completed": 50}'
        },
        
        # Community Achievements
        {
            'name': 'Community Explorer',
            'description': 'Join your first investment room',
            'icon': '🚀',
            'category': 'community',
            'points': 10,
            'requirements': '{"rooms_joined": 1}'
        },
        {
            'name': 'First Post',
            'description': 'Share your first post with the community',
            'icon': '✍️',
            'category': 'community',
            'points': 20,
            'requirements': '{"posts_created": 1}'
        },
        {
            'name': 'Active Contributor',
            'description': 'Create 25 posts',
            'icon': '💬',
            'category': 'community',
            'points': 100,
            'requirements': '{"posts_created": 25}'
        },
        {
            'name': 'Community Leader',
            'description': 'Create 100 posts',
            'icon': '⭐',
            'category': 'community',
            'points': 300,
            'requirements': '{"posts_created": 100}'
        },
        {
            'name': 'Networker',
            'description': 'Connect with 10 fellow physicians',
            'icon': '🤝',
            'category': 'community',
            'points': 50,
            'requirements': '{"followers": 10}'
        },
        {
            'name': 'Influencer',
            'description': 'Build a following of 100 physicians',
            'icon': '🌟',
            'category': 'community',
            'points': 200,
            'requirements': '{"followers": 100}'
        },
        
        # Investing Milestones
        {
            'name': 'First Trade',
            'description': 'Execute your first virtual trade',
            'icon': '💹',
            'category': 'investing',
            'points': 15,
            'requirements': '{"portfolio_transactions": 1}'
        },
        {
            'name': 'Portfolio Builder',
            'description': 'Execute 50 virtual trades',
            'icon': '📊',
            'category': 'investing',
            'points': 150,
            'requirements': '{"portfolio_transactions": 50}'
        },
        
        # Milestone Achievements
        {
            'name': 'Welcome to MedInvest',
            'description': 'Complete your profile',
            'icon': '👋',
            'category': 'milestone',
            'points': 5,
            'requirements': '{}'
        },
        {
            'name': 'Week Streak',
            'description': 'Log in for 7 consecutive days',
            'icon': '🔥',
            'category': 'milestone',
            'points': 50,
            'requirements': '{"login_streak": 7}'
        },
        {
            'name': 'Month Veteran',
            'description': 'Active member for 30 days',
            'icon': '📅',
            'category': 'milestone',
            'points': 100,
            'requirements': '{"days_active": 30}'
        },
    ]
    
    created_count = 0
    for achievement_data in achievements_data:
        existing = Achievement.query.filter_by(name=achievement_data['name']).first()
        if not existing:
            achievement = Achievement(**achievement_data)
            db.session.add(achievement)
            created_count += 1
    
    db.session.commit()
    logging.info(f"Created {created_count} achievements")


def create_trending_topics():
    """Create initial trending topics"""
    topics = [
        'retirement', 'studentloans', 'taxplanning', 'realestate', 
        'stockmarket', 'sidehustle', 'backdoorroth', 'indexfunds',
        'practiceownership', 'PSLF', 'estateplanning', 'disability-insurance',
        'cryptocurrency', 'bonds', 'dividends', 'FIRE'
    ]
    
    created_count = 0
    for tag in topics:
        existing = TrendingTopic.query.filter_by(tag=tag.lower()).first()
        if not existing:
            topic = TrendingTopic(
                tag=tag.lower(),
                mention_count=0,
                post_count=0,
                trend_score=0.0
            )
            db.session.add(topic)
            created_count += 1
    
    db.session.commit()
    logging.info(f"Created {created_count} trending topics")


def init_database():
    """Initialize database with all new features"""
    with app.app_context():
        # Create all tables
        db.create_all()
        logging.info("Database tables created")
        
        # Populate data
        create_investment_rooms()
        create_achievements()
        create_trending_topics()
        
        logging.info("Database initialization complete!")


if __name__ == '__main__':
    init_database()
