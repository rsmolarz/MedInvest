"""
Seed Database Script
Run with: python seed.py
"""
from datetime import datetime, timedelta
import random

from app import app, db
from models import (User, Room, Post, Comment, ExpertAMA,
                   InvestmentDeal, Course, CourseModule, Event)


def seed_database():
    """Populate database with sample data"""
    with app.app_context():
        print("Seeding database...")
        
        # =================================================================
        # USERS
        # =================================================================
        print("  Creating users...")
        
        # Admin user
        admin = User.query.filter_by(email='admin@medinvest.com').first()
        if not admin:
            admin = User(
                email='admin@medinvest.com',
                first_name='Admin',
                last_name='User',
                medical_license='ADMIN001',
                specialty='internal_medicine',
                role='admin',
                is_verified=True,
                subscription_tier='premium',
                points=5000,
                level=10
            )
            admin.set_password('admin123')
            admin.generate_referral_code()
            db.session.add(admin)
        
        # Demo user
        demo = User.query.filter_by(email='demo@medinvest.com').first()
        if not demo:
            demo = User(
                email='demo@medinvest.com',
                first_name='Demo',
                last_name='Doctor',
                medical_license='DEMO001',
                specialty='cardiology',
                is_verified=True,
                points=500,
                level=2
            )
            demo.set_password('demo123')
            demo.generate_referral_code()
            db.session.add(demo)
        
        # Sample users
        specialties = ['cardiology', 'anesthesiology', 'radiology', 'surgery', 
                      'internal_medicine', 'emergency_medicine', 'pediatrics',
                      'dermatology', 'orthopedics', 'psychiatry']
        
        first_names = ['James', 'Sarah', 'Michael', 'Emily', 'David', 'Jessica',
                      'Robert', 'Amanda', 'William', 'Ashley']
        last_names = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 
                     'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez']
        
        for i in range(10):
            email = f'doctor{i+1}@example.com'
            if not User.query.filter_by(email=email).first():
                user = User(
                    email=email,
                    first_name=first_names[i],
                    last_name=last_names[i],
                    medical_license=f'MD{100+i}',
                    specialty=random.choice(specialties),
                    is_verified=random.choice([True, False]),
                    points=random.randint(50, 2000),
                    level=random.randint(1, 5)
                )
                user.set_password('password123')
                user.generate_referral_code()
                db.session.add(user)
        
        db.session.commit()
        
        # =================================================================
        # ROOMS
        # =================================================================
        print("  Creating rooms...")
        
        rooms_data = [
            # Strategy rooms
            ('Index Fund Investors', 'index-funds', 'Strategy', 'Passive investing with index funds', 'chart-line'),
            ('Real Estate Physicians', 'real-estate', 'Strategy', 'Real estate investing strategies', 'building'),
            ('FIRE Movement', 'fire', 'Strategy', 'Financial Independence, Retire Early', 'fire'),
            ('Dividend Growth', 'dividends', 'Strategy', 'Building passive income through dividends', 'coins'),
            ('Tax Optimization', 'tax-optimization', 'Strategy', 'Minimize taxes legally', 'calculator'),
            
            # Specialty rooms
            ('Cardiology Investors', 'cardiology-investors', 'Specialty', 'Investing for cardiologists', 'heart'),
            ('Anesthesia Finance', 'anesthesia-finance', 'Specialty', 'Financial strategies for anesthesiologists', 'syringe'),
            ('Surgery & Wealth', 'surgery-wealth', 'Specialty', 'Surgeons building wealth', 'cut'),
            ('EM Physicians', 'emergency-medicine', 'Specialty', 'ER docs discussing finance', 'ambulance'),
            
            # Career stage rooms
            ('Residents & Fellows', 'residents-fellows', 'Career Stage', 'Early career physicians', 'graduation-cap'),
            ('Attendings Lounge', 'attendings', 'Career Stage', 'Established physicians', 'user-md'),
            ('Pre-Retirement', 'pre-retirement', 'Career Stage', 'Planning for retirement', 'umbrella-beach'),
        ]
        
        for name, slug, category, description, icon in rooms_data:
            existing = Room.query.filter((Room.slug == slug) | (Room.name == name)).first()
            if not existing:
                room = Room(
                    name=name,
                    slug=slug,
                    category=category,
                    description=description,
                    icon=icon,
                    member_count=random.randint(100, 2000)
                )
                db.session.add(room)
        
        db.session.commit()
        
        # =================================================================
        # EXPERT AMAs
        # =================================================================
        print("  Creating AMAs...")
        
        amas_data = [
            {
                'expert_name': 'Dr. James Dahle',
                'expert_title': 'Founder, White Coat Investor',
                'expert_bio': 'Board-certified emergency physician and founder of the White Coat Investor blog and podcast.',
                'title': 'Building Wealth as a Physician: Back to Basics',
                'description': 'Join Dr. Dahle for a comprehensive discussion on wealth building fundamentals for medical professionals.',
                'scheduled_for': datetime.utcnow() + timedelta(days=7),
                'status': 'scheduled',
            },
            {
                'expert_name': 'Dr. Leif Dahleen',
                'expert_title': 'Physician on FIRE',
                'expert_bio': 'Anesthesiologist who achieved financial independence and retired early.',
                'title': 'Achieving FIRE as a Physician',
                'description': 'Learn strategies for financial independence and early retirement from someone who has done it.',
                'scheduled_for': datetime.utcnow() + timedelta(days=14),
                'status': 'scheduled',
            },
            {
                'expert_name': 'Dr. Peter Kim',
                'expert_title': 'Passive Income MD',
                'expert_bio': 'Physician investor focused on real estate and passive income strategies.',
                'title': 'Real Estate Investing for Busy Physicians',
                'description': 'Discover how to invest in real estate without sacrificing your clinical career.',
                'scheduled_for': datetime.utcnow() - timedelta(days=7),
                'status': 'ended',
                'recording_url': 'https://example.com/recording-1',
            },
        ]
        
        for ama_data in amas_data:
            if not ExpertAMA.query.filter_by(expert_name=ama_data['expert_name']).first():
                ama = ExpertAMA(
                    expert_name=ama_data['expert_name'],
                    expert_title=ama_data['expert_title'],
                    expert_bio=ama_data['expert_bio'],
                    title=ama_data['title'],
                    description=ama_data['description'],
                    scheduled_for=ama_data['scheduled_for'],
                    status=ama_data['status'],
                    recording_url=ama_data.get('recording_url'),
                    participant_count=random.randint(50, 500),
                    question_count=random.randint(20, 100)
                )
                db.session.add(ama)
        
        db.session.commit()
        
        # =================================================================
        # INVESTMENT DEALS
        # =================================================================
        print("  Creating deals...")
        
        deals_data = [
            {
                'title': 'Medical Office Building - Austin, TX',
                'description': 'Class A medical office building in a rapidly growing Austin suburb. Long-term lease with established multi-specialty group.',
                'deal_type': 'real_estate',
                'minimum_investment': 50000,
                'target_raise': 5000000,
                'current_raised': 3200000,
                'projected_return': '15-18% IRR',
                'investment_term': '5-7 years',
                'location': 'Austin, TX',
                'sponsor_name': 'MedReal Partners',
                'status': 'active',
                'is_featured': True,
            },
            {
                'title': 'Physician Syndicate Fund III',
                'description': 'Diversified fund investing in healthcare real estate, private practices, and medical startups.',
                'deal_type': 'fund',
                'minimum_investment': 100000,
                'target_raise': 25000000,
                'current_raised': 15000000,
                'projected_return': '12-15% annually',
                'investment_term': '7-10 years',
                'sponsor_name': 'DocVentures Capital',
                'status': 'active',
                'is_featured': True,
            },
            {
                'title': 'Dermatology Practice Acquisition',
                'description': 'Opportunity to invest in the acquisition of a well-established dermatology practice in Florida.',
                'deal_type': 'practice',
                'minimum_investment': 25000,
                'target_raise': 2000000,
                'current_raised': 800000,
                'projected_return': '20-25% IRR',
                'investment_term': '5 years',
                'location': 'Tampa, FL',
                'sponsor_name': 'DermCapital LLC',
                'status': 'active',
            },
        ]
        
        for deal_data in deals_data:
            if not InvestmentDeal.query.filter_by(title=deal_data['title']).first():
                deal = InvestmentDeal(
                    title=deal_data['title'],
                    description=deal_data['description'],
                    deal_type=deal_data['deal_type'],
                    minimum_investment=deal_data['minimum_investment'],
                    target_raise=deal_data['target_raise'],
                    current_raised=deal_data['current_raised'],
                    projected_return=deal_data['projected_return'],
                    investment_term=deal_data['investment_term'],
                    location=deal_data.get('location'),
                    sponsor_name=deal_data['sponsor_name'],
                    status=deal_data['status'],
                    is_featured=deal_data.get('is_featured', False),
                    view_count=random.randint(100, 1000),
                    interest_count=random.randint(10, 100),
                )
                db.session.add(deal)
        
        db.session.commit()
        
        # =================================================================
        # COURSES
        # =================================================================
        print("  Creating courses...")
        
        courses_data = [
            {
                'title': 'Physician Finance Fundamentals',
                'description': 'A comprehensive course covering the basics of personal finance for medical professionals.',
                'instructor_name': 'Dr. James Dahle',
                'price': 0,
                'difficulty_level': 'beginner',
                'is_published': True,
                'is_featured': True,
                'modules': [
                    {'title': 'Understanding Your Paycheck', 'duration': 15},
                    {'title': 'Budgeting Basics', 'duration': 20},
                    {'title': 'Emergency Fund Essentials', 'duration': 15},
                    {'title': 'Understanding Debt', 'duration': 25},
                    {'title': 'Introduction to Investing', 'duration': 30},
                ]
            },
            {
                'title': 'Real Estate Investing Masterclass',
                'description': 'Learn how to build passive income through real estate investments.',
                'instructor_name': 'Dr. Peter Kim',
                'price': 299,
                'difficulty_level': 'intermediate',
                'is_published': True,
                'modules': [
                    {'title': 'Real Estate Fundamentals', 'duration': 30},
                    {'title': 'Analyzing Properties', 'duration': 45},
                    {'title': 'Financing Strategies', 'duration': 35},
                    {'title': 'Syndications & REITs', 'duration': 40},
                    {'title': 'Tax Advantages', 'duration': 25},
                ]
            },
            {
                'title': 'Advanced Tax Strategies',
                'description': 'Maximize your tax efficiency with advanced strategies for high-income earners.',
                'instructor_name': 'CPA Michael Chen',
                'price': 199,
                'difficulty_level': 'advanced',
                'is_published': True,
                'modules': [
                    {'title': 'Tax-Advantaged Accounts Deep Dive', 'duration': 35},
                    {'title': 'Backdoor Roth Strategies', 'duration': 30},
                    {'title': 'Business Entity Selection', 'duration': 40},
                    {'title': 'Charitable Giving Strategies', 'duration': 25},
                ]
            },
        ]
        
        for course_data in courses_data:
            if not Course.query.filter_by(title=course_data['title']).first():
                total_duration = sum(m['duration'] for m in course_data['modules'])
                course = Course(
                    title=course_data['title'],
                    description=course_data['description'],
                    instructor_name=course_data['instructor_name'],
                    price=course_data['price'],
                    difficulty_level=course_data['difficulty_level'],
                    is_published=course_data['is_published'],
                    is_featured=course_data.get('is_featured', False),
                    total_modules=len(course_data['modules']),
                    total_duration_minutes=total_duration,
                    enrolled_count=random.randint(50, 500)
                )
                db.session.add(course)
                db.session.commit()
                
                # Add modules
                for i, mod in enumerate(course_data['modules']):
                    module = CourseModule(
                        course_id=course.id,
                        title=mod['title'],
                        duration_minutes=mod['duration'],
                        order_index=i
                    )
                    db.session.add(module)
        
        db.session.commit()
        
        # =================================================================
        # EVENTS
        # =================================================================
        print("  Creating events...")
        
        events_data = [
            {
                'title': 'Physician Wealth Summit 2026',
                'description': 'The premier conference for physician investors. Network, learn, and grow your wealth.',
                'is_virtual': False,
                'venue_name': 'JW Marriott Austin',
                'venue_address': '110 E 2nd St, Austin, TX 78701',
                'start_date': datetime.utcnow() + timedelta(days=90),
                'end_date': datetime.utcnow() + timedelta(days=92),
                'regular_price': 599,
                'early_bird_price': 449,
                'early_bird_ends': datetime.utcnow() + timedelta(days=60),
                'max_attendees': 500,
                'is_published': True,
                'is_featured': True,
            },
            {
                'title': 'Virtual Real Estate Investing Workshop',
                'description': 'Learn the fundamentals of real estate investing from the comfort of your home.',
                'is_virtual': True,
                'start_date': datetime.utcnow() + timedelta(days=21),
                'end_date': datetime.utcnow() + timedelta(days=21, hours=3),
                'regular_price': 99,
                'max_attendees': 200,
                'is_published': True,
            },
        ]
        
        for event_data in events_data:
            if not Event.query.filter_by(title=event_data['title']).first():
                event = Event(
                    title=event_data['title'],
                    description=event_data['description'],
                    is_virtual=event_data['is_virtual'],
                    venue_name=event_data.get('venue_name'),
                    venue_address=event_data.get('venue_address'),
                    start_date=event_data['start_date'],
                    end_date=event_data.get('end_date'),
                    regular_price=event_data['regular_price'],
                    early_bird_price=event_data.get('early_bird_price'),
                    early_bird_ends=event_data.get('early_bird_ends'),
                    max_attendees=event_data.get('max_attendees'),
                    is_published=event_data.get('is_published', False),
                    is_featured=event_data.get('is_featured', False),
                    current_attendees=random.randint(10, 100)
                )
                db.session.add(event)
        
        db.session.commit()
        
        # =================================================================
        # SAMPLE POSTS
        # =================================================================
        print("  Creating sample posts...")
        
        users = User.query.all()
        rooms = Room.query.all()
        
        post_contents = [
            "Just maxed out my 401k and backdoor Roth for the year. Feels good to be on track!",
            "Anyone have experience with syndication deals? Looking at my first one and would appreciate advice.",
            "Closed on my first rental property today! A duplex in a college town. Excited and nervous.",
            "What's everyone's asset allocation? I'm 60/40 stocks/bonds but wondering if I should adjust.",
            "PSA: Don't forget about your HSA - triple tax advantaged and often overlooked.",
            "Thinking about hiring a fee-only financial advisor. Any recommendations?",
            "Just paid off my student loans! It's been a 10-year journey but finally debt free.",
            "How do you all handle the work-life balance while also trying to build wealth?",
            "Started learning about tax-loss harvesting. Game changer for taxable accounts.",
            "Anyone here doing real estate through their self-directed solo 401k?",
        ]
        
        if users and rooms:
            for i, content in enumerate(post_contents):
                user = random.choice(users)
                room = random.choice(rooms)
                
                if not Post.query.filter_by(content=content).first():
                    post = Post(
                        author_id=user.id,
                        room_id=room.id,
                        content=content,
                        is_anonymous=random.choice([True, False]),
                        upvotes=random.randint(5, 100),
                        downvotes=random.randint(0, 10),
                        view_count=random.randint(50, 500),
                        comment_count=random.randint(2, 20),
                        created_at=datetime.utcnow() - timedelta(hours=random.randint(1, 72))
                    )
                    if post.is_anonymous:
                        post.anonymous_name = f"Anonymous {user.specialty.replace('_', ' ').title() if user.specialty else 'Physician'}"
                    db.session.add(post)
            
            db.session.commit()
        
        print("Database seeded successfully!")


if __name__ == '__main__':
    seed_database()
