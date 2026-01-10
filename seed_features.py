"""Seed database with investment rooms and achievements."""
from app import app, db
from models import InvestmentRoom, Achievement

def seed_rooms():
    """Create initial investment rooms."""
    rooms_data = [
        # Specialty Rooms
        {'name': 'Cardiology Practice Owners', 'slug': 'cardiology', 'category': 'specialty', 'icon': '🫀', 'description': 'Investment strategies for cardiologists, from practice ownership to real estate.'},
        {'name': 'Orthopedic Surgeons', 'slug': 'orthopedics', 'category': 'specialty', 'icon': '🦴', 'description': 'ASC investments, practice valuation, and wealth building for orthopedic surgeons.'},
        {'name': 'Dermatology & Med Spa', 'slug': 'dermatology', 'category': 'specialty', 'icon': '✨', 'description': 'Practice ownership, med spa investments, and side income for dermatologists.'},
        {'name': 'Emergency Medicine', 'slug': 'emergency', 'category': 'specialty', 'icon': '🚨', 'description': 'Shift-based income strategies, locums investing, and wealth building for EM docs.'},
        {'name': 'Anesthesiology', 'slug': 'anesthesia', 'category': 'specialty', 'icon': '💉', 'description': 'Partnership buy-ins, pain management investments, and financial planning.'},
        {'name': 'Primary Care & FM', 'slug': 'primary-care', 'category': 'specialty', 'icon': '🩺', 'description': 'DPC models, practice transitions, and investments for family medicine physicians.'},
        
        # Career Stage Rooms
        {'name': 'Residents & Fellows', 'slug': 'residents', 'category': 'career_stage', 'icon': '🎓', 'description': 'Starting from $0: student loans, first investments, and building habits early.'},
        {'name': 'Early Career (1-5 years)', 'slug': 'early-career', 'category': 'career_stage', 'icon': '🚀', 'description': 'Loan payoff vs investing, first home, partnership buy-ins, and building wealth.'},
        {'name': 'Mid Career (5-15 years)', 'slug': 'mid-career', 'category': 'career_stage', 'icon': '📈', 'description': 'Scaling investments, practice ownership, real estate syndications, and tax planning.'},
        {'name': 'Late Career & FIRE', 'slug': 'late-career', 'category': 'career_stage', 'icon': '🏝️', 'description': 'Exit strategies, retirement planning, wealth preservation, and FIRE discussions.'},
        
        # Topic Rooms
        {'name': 'Real Estate Investing', 'slug': 'real-estate', 'category': 'topic', 'icon': '🏠', 'description': 'Rental properties, syndications, REITs, and real estate strategies for physicians.'},
        {'name': 'Tax Planning & Optimization', 'slug': 'tax-planning', 'category': 'topic', 'icon': '📊', 'description': 'Tax strategies, deductions, retirement accounts, and entity structuring.'},
        {'name': 'Stock Market & Index Investing', 'slug': 'stocks', 'category': 'topic', 'icon': '📈', 'description': 'Individual stocks, ETFs, index investing, and portfolio strategies.'},
        {'name': 'Student Loan Strategies', 'slug': 'student-loans', 'category': 'topic', 'icon': '🎓', 'description': 'PSLF, refinancing, payoff strategies, and loan forgiveness programs.'},
    ]
    
    created = 0
    for room_data in rooms_data:
        existing = InvestmentRoom.query.filter_by(slug=room_data['slug']).first()
        if not existing:
            room = InvestmentRoom(**room_data)
            db.session.add(room)
            created += 1
    
    db.session.commit()
    print(f"Created {created} investment rooms")


def seed_achievements():
    """Create initial achievements."""
    achievements_data = [
        # Engagement Achievements
        {'code': 'first_post', 'name': 'First Steps', 'description': 'Create your first post', 'icon': '✍️', 'category': 'engagement', 'tier': 'bronze', 'points': 10},
        {'code': 'post_10', 'name': 'Consistent Contributor', 'description': 'Create 10 posts', 'icon': '📝', 'category': 'engagement', 'tier': 'silver', 'points': 25},
        {'code': 'post_50', 'name': 'Prolific Poster', 'description': 'Create 50 posts', 'icon': '📚', 'category': 'engagement', 'tier': 'gold', 'points': 100},
        {'code': 'first_comment', 'name': 'Joining the Conversation', 'description': 'Leave your first comment', 'icon': '💬', 'category': 'engagement', 'tier': 'bronze', 'points': 5},
        {'code': 'likes_received_10', 'name': 'Appreciated', 'description': 'Receive 10 likes on your posts', 'icon': '❤️', 'category': 'engagement', 'tier': 'bronze', 'points': 15},
        {'code': 'likes_received_100', 'name': 'Community Favorite', 'description': 'Receive 100 likes on your posts', 'icon': '🌟', 'category': 'engagement', 'tier': 'gold', 'points': 75},
        
        # Community Achievements
        {'code': 'first_room', 'name': 'Room Explorer', 'description': 'Join your first investment room', 'icon': '🚪', 'category': 'community', 'tier': 'bronze', 'points': 10},
        {'code': 'rooms_5', 'name': 'Active Participant', 'description': 'Join 5 investment rooms', 'icon': '🏠', 'category': 'community', 'tier': 'silver', 'points': 25},
        {'code': 'first_follower', 'name': 'Building Network', 'description': 'Gain your first follower', 'icon': '👥', 'category': 'community', 'tier': 'bronze', 'points': 10},
        {'code': 'followers_50', 'name': 'Thought Leader', 'description': 'Gain 50 followers', 'icon': '🎤', 'category': 'community', 'tier': 'gold', 'points': 100},
        {'code': 'helped_others_5', 'name': 'Helpful Colleague', 'description': 'Have 5 of your answers marked as helpful', 'icon': '🤝', 'category': 'community', 'tier': 'silver', 'points': 30},
        
        # Learning Achievements
        {'code': 'complete_module', 'name': 'Lifelong Learner', 'description': 'Complete your first learning module', 'icon': '📖', 'category': 'learning', 'tier': 'bronze', 'points': 15},
        {'code': 'complete_5_modules', 'name': 'Dedicated Student', 'description': 'Complete 5 learning modules', 'icon': '🎯', 'category': 'learning', 'tier': 'silver', 'points': 40},
        {'code': 'complete_all_modules', 'name': 'Investment Scholar', 'description': 'Complete all available modules', 'icon': '🏆', 'category': 'learning', 'tier': 'platinum', 'points': 200},
        
        # Investing Achievements
        {'code': 'first_deal', 'name': 'Deal Sharer', 'description': 'Share your first investment deal', 'icon': '💼', 'category': 'investing', 'tier': 'bronze', 'points': 20},
        {'code': 'deals_reviewed_5', 'name': 'Due Diligence Pro', 'description': 'Review 5 investment deals', 'icon': '🔍', 'category': 'investing', 'tier': 'silver', 'points': 30},
        {'code': 'portfolio_started', 'name': 'Portfolio Beginner', 'description': 'Start tracking your portfolio', 'icon': '📊', 'category': 'investing', 'tier': 'bronze', 'points': 10},
        {'code': 'millionaire_md', 'name': 'Millionaire MD', 'description': 'Reach $1M tracked net worth', 'icon': '💎', 'category': 'investing', 'tier': 'platinum', 'points': 500, 'is_secret': True},
    ]
    
    created = 0
    for ach_data in achievements_data:
        existing = Achievement.query.filter_by(code=ach_data['code']).first()
        if not existing:
            achievement = Achievement(**ach_data)
            db.session.add(achievement)
            created += 1
    
    db.session.commit()
    print(f"Created {created} achievements")


if __name__ == '__main__':
    with app.app_context():
        seed_rooms()
        seed_achievements()
        print("Database seeding complete!")
