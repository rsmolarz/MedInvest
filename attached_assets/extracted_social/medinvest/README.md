# MedInvest - Investment Community for Physicians

## Quick Start (Replit)

1. Upload all files to Replit
2. Click "Run" - dependencies install automatically
3. Run `python seed.py` in Shell to populate demo data
4. Open the app URL

## Test Accounts
- **Admin:** admin@medinvest.com / admin123
- **Demo:** demo@medinvest.com / demo123

## File Structure
```
medinvest/
├── app.py              # Application factory
├── models.py           # All database models
├── seed.py             # Demo data script
├── requirements.txt    # Python dependencies
├── routes/             # 13 blueprint modules
│   ├── main.py         # Feed, profile, dashboard
│   ├── auth.py         # Login, register, logout
│   ├── rooms.py        # Discussion rooms
│   ├── ama.py          # Expert AMAs
│   ├── deals.py        # Investment marketplace
│   ├── subscription.py # Premium membership
│   ├── courses.py      # Educational content
│   ├── events.py       # Conferences & networking
│   ├── mentorship.py   # Peer mentorship
│   ├── referral.py     # Referral program
│   ├── portfolio.py    # Portfolio tracking
│   ├── ai.py           # AI assistant
│   ├── admin.py        # Platform admin
│   └── errors.py       # Error handlers
└── templates/          # 37 HTML templates
```

## Features
- 🔐 User authentication with specialty selection
- 💬 14 investment discussion rooms
- 👤 Anonymous posting with specialty tags
- 🎯 Points & gamification system
- 📊 Expert AMAs with Q&A
- 💰 Vetted investment deal marketplace
- 📚 Educational courses
- 📅 Events & conferences
- 🤝 Peer mentorship program
- 🎁 Referral rewards
- 📈 Portfolio tracking & analysis
- 🤖 AI financial assistant
- 👑 Premium membership tiers

## Optional: Enable AI
Set `ANTHROPIC_API_KEY` environment variable for full AI capabilities.
