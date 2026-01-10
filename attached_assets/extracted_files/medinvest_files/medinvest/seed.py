"""
Seed Database Script
Run with: python seed.py
"""
from datetime import datetime, timedelta
import random

from app import create_app, db
from models import (User, Room, Post, Comment, ExpertAMA, AMAStatus, 
                   InvestmentDeal, DealStatus, Course, CourseModule,
                   Event, SubscriptionTier)


def seed_database():
    """Populate database with sample data"""
    app = create_app()
    
    with app.app_context():
        print("🌱 Seeding database...")
        
        # Clear existing data (optional - comment out to preserve)
        # db.drop_all()
        # db.create_all()
        
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
                specialty='internal_medicine',
                is_admin=True,
                is_verified=True,
                subscription_tier=SubscriptionTier.PREMIUM,
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
            if not Room.query.filter_by(slug=slug).first():
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
        # POSTS
        # =================================================================
        print("  Creating posts...")
        
        posts_content = [
            ("Just hit my first $1M in index funds!", "Started during residency with just $500/month into VTSAX. Consistency really is key. Took about 12 years with market growth. AMA!", False),
            ("Backdoor Roth question", "Is it worth doing a backdoor Roth if I already have a pre-tax IRA balance? The pro-rata rule seems complicated.", False),
            ("Real estate vs stocks debate", "I keep going back and forth. Stocks are so easy with index funds, but real estate has tax benefits and leverage. What's your allocation?", False),
            ("First syndication investment - nervous!", "Just committed $50k to a medical office building syndication. Projected 15% annual returns. Anyone have experience with these?", True),
            ("Student loan payoff celebration", "After 8 years of aggressive payments, I'm finally debt free! $380k paid off. Time to max out all retirement accounts.", False),
            ("Disability insurance question", "Got quoted $400/month for own-occupation disability. Is this reasonable for a surgical subspecialty?", True),
            ("Side gig income ideas", "Looking for ways to supplement income without taking more call. Any physicians doing consulting, expert witness work, or other side gigs?", False),
            ("401k vs taxable brokerage", "Already maxing 401k, backdoor Roth, and HSA. Should extra money go to mega backdoor Roth or taxable account?", False),
            ("New attending - budget help", "Just started as an attending making $350k. Coming from $55k resident salary. How do I avoid lifestyle creep?", False),
            ("PSLF success story", "10 years, 120 payments, $450k forgiven! It's real, people. Keep those certifications up to date.", False),
        ]
        
        users = User.query.all()
        rooms = Room.query.all()
        
        for content_tuple in posts_content:
            title = content_tuple[0][:50] if len(content_tuple) > 0 else None
            
            post = Post(
                user_id=random.choice(users).id,
                room_id=random.choice(rooms).id if rooms else None,
                title=title,
                content=content_tuple[1] if len(content_tuple) > 1 else content_tuple[0],
                is_anonymous=content_tuple[2] if len(content_tuple) > 2 else random.choice([True, False]),
                anonymous_name=f"Anonymous {random.choice(['Cardiologist', 'Surgeon', 'Internist', 'Radiologist', 'Anesthesiologist'])}" if (len(content_tuple) > 2 and content_tuple[2]) else None,
                upvotes=random.randint(10, 300),
                comment_count=random.randint(5, 50),
                created_at=datetime.utcnow() - timedelta(days=random.randint(1, 30))
            )
            db.session.add(post)
        
        db.session.commit()
        
        # =================================================================
        # EXPERT AMAs
        # =================================================================
        print("  Creating AMAs...")
        
        amas_data = [
            ("Tax Strategies for High-Income Physicians", "Dr. Michael Chen, CPA", "Tax Attorney & Physician", 
             "Learn advanced tax strategies specifically for physician income levels.", 7, False),
            ("Building a Real Estate Portfolio", "Sarah Martinez, MD", "Radiologist & RE Investor",
             "How I built a $2M real estate portfolio while practicing full-time.", 14, False),
            ("FIRE for Physicians", "Dr. James White", "Retired Cardiologist at 50",
             "Achieving financial independence and retiring early from medicine.", 21, True),
            ("Student Loan Mastery", "Amanda Foster, CFP", "Physician Financial Planner",
             "PSLF, refinancing, and payoff strategies for six-figure loans.", 3, False),
            ("Physician Side Gigs", "Dr. Robert Kim", "EM Physician & Entrepreneur",
             "Building income streams outside of clinical practice.", 28, False),
        ]
        
        for title, expert, expert_title, description, days_out, is_premium in amas_data:
            if not ExpertAMA.query.filter_by(title=title).first():
                ama = ExpertAMA(
                    title=title,
                    expert_name=expert,
                    expert_title=expert_title,
                    description=description,
                    scheduled_for=datetime.utcnow() + timedelta(days=days_out),
                    duration_minutes=60,
                    is_premium_only=is_premium,
                    status=AMAStatus.SCHEDULED,
                    participant_count=random.randint(50, 300)
                )
                db.session.add(ama)
        
        # Add a past AMA with recording
        past_ama = ExpertAMA(
            title="Index Fund Investing 101",
            expert_name="Dr. William Bogle",
            expert_title="Physician & Author",
            description="The basics of passive index fund investing for physicians.",
            scheduled_for=datetime.utcnow() - timedelta(days=14),
            duration_minutes=60,
            is_premium_only=False,
            status=AMAStatus.ENDED,
            recording_url="https://example.com/recording",
            participant_count=450,
            question_count=67
        )
        db.session.add(past_ama)
        
        db.session.commit()
        
        # =================================================================
        # INVESTMENT DEALS
        # =================================================================
        print("  Creating deals...")
        
        deals_data = [
            ("Medical Office Building - Austin, TX", "real_estate", 50000, 2500000, 
             "12-15% projected", "5 years", "Austin, TX", "Physician Capital Partners", True),
            ("Healthcare Tech Fund III", "fund", 100000, 10000000,
             "15-20% IRR target", "7 years", None, "MedVenture Capital", False),
            ("Ambulatory Surgery Center JV", "syndicate", 250000, 5000000,
             "18-22% projected", "10 years", "Phoenix, AZ", "Surgical Partners LLC", True),
            ("Primary Care Practice Acquisition", "practice", 150000, 1500000,
             "8x multiple target", "5 years", "Denver, CO", "Primary Care Holdings", False),
            ("Senior Living Development", "real_estate", 75000, 8000000,
             "14-16% projected", "6 years", "Tampa, FL", "Healthcare RE Group", False),
        ]
        
        for title, deal_type, minimum, target, returns, term, location, sponsor, featured in deals_data:
            if not InvestmentDeal.query.filter_by(title=title).first():
                deal = InvestmentDeal(
                    title=title,
                    description=f"Investment opportunity in {deal_type.replace('_', ' ')}. {sponsor} is seeking physician investors for this {term} investment with {returns} returns.",
                    deal_type=deal_type,
                    minimum_investment=minimum,
                    target_raise=target,
                    current_raised=random.randint(0, int(target * 0.7)),
                    projected_return=returns,
                    investment_term=term,
                    location=location,
                    sponsor_name=sponsor,
                    sponsor_bio=f"{sponsor} has completed 15+ deals with physician investors over the past decade.",
                    sponsor_contact=f"deals@{sponsor.lower().replace(' ', '')}.com",
                    status=DealStatus.ACTIVE,
                    is_featured=featured,
                    view_count=random.randint(100, 1000),
                    interest_count=random.randint(10, 100)
                )
                db.session.add(deal)
        
        db.session.commit()
        
        # =================================================================
        # COURSES
        # =================================================================
        print("  Creating courses...")
        
        courses_data = [
            ("Physician Finance Fundamentals", "Master the basics of personal finance for doctors", 
             "Dr. Financial", 199, True),
            ("Real Estate Investing for Physicians", "Build passive income through real estate",
             "Sarah RE, MD", 299, True),
            ("Advanced Tax Strategies", "Minimize taxes and keep more of what you earn",
             "Michael Tax, CPA", 399, False),
            ("Building Your Investment Portfolio", "From zero to diversified portfolio",
             "Dr. Portfolio", 249, False),
        ]
        
        for title, description, instructor, price, featured in courses_data:
            if not Course.query.filter_by(title=title).first():
                course = Course(
                    title=title,
                    description=description,
                    instructor_name=instructor,
                    price=price,
                    is_published=True,
                    is_featured=featured,
                    enrolled_count=random.randint(50, 500),
                    total_modules=5,
                    total_duration_minutes=180
                )
                db.session.add(course)
                db.session.flush()  # Get the course ID
                
                # Add modules
                module_titles = [
                    "Introduction & Overview",
                    "Core Concepts",
                    "Practical Application",
                    "Advanced Strategies",
                    "Action Plan & Next Steps"
                ]
                
                for i, mod_title in enumerate(module_titles):
                    module = CourseModule(
                        course_id=course.id,
                        title=mod_title,
                        description=f"Module {i+1} of {title}",
                        duration_minutes=random.randint(25, 45),
                        order_index=i
                    )
                    db.session.add(module)
        
        db.session.commit()
        
        # =================================================================
        # EVENTS
        # =================================================================
        print("  Creating events...")
        
        events_data = [
            ("Physician Wealth Summit 2024", "Annual conference for physician investors", 
             True, 299, 199, 45),
            ("Real Estate Networking Virtual", "Monthly virtual networking for RE investors",
             True, 0, None, 14),
            ("Tax Planning Workshop", "Year-end tax planning strategies",
             True, 99, 79, 30),
            ("WCI Conference", "White Coat Investor annual conference",
             False, 499, 399, 60, "Las Vegas Convention Center", "Las Vegas, NV"),
        ]
        
        for event_tuple in events_data:
            title = event_tuple[0]
            if not Event.query.filter_by(title=title).first():
                event = Event(
                    title=title,
                    description=event_tuple[1],
                    is_virtual=event_tuple[2],
                    regular_price=event_tuple[3],
                    early_bird_price=event_tuple[4],
                    early_bird_ends=datetime.utcnow() + timedelta(days=event_tuple[5] - 7) if event_tuple[4] else None,
                    start_date=datetime.utcnow() + timedelta(days=event_tuple[5]),
                    end_date=datetime.utcnow() + timedelta(days=event_tuple[5], hours=8),
                    venue_name=event_tuple[6] if len(event_tuple) > 6 else None,
                    venue_address=event_tuple[7] if len(event_tuple) > 7 else None,
                    is_published=True,
                    is_featured=True if event_tuple[3] > 200 else False,
                    max_attendees=500 if not event_tuple[2] else None,
                    current_attendees=random.randint(20, 200)
                )
                db.session.add(event)
        
        db.session.commit()
        
        print("✅ Database seeded successfully!")
        print("\n📝 Test Accounts:")
        print("   Admin: admin@medinvest.com / admin123")
        print("   Demo:  demo@medinvest.com / demo123")


if __name__ == '__main__':
    seed_database()
