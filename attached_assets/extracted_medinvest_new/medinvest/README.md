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
├── models.py           # All database models (20+)
├── seed.py             # Demo data script
├── requirements.txt    # Python dependencies
├── routes/             # 16 blueprint modules
│   ├── main.py         # Feed, profile, search, hashtags
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
│   ├── media.py        # Image/video uploads
│   ├── notifications.py # Notification system
│   └── errors.py       # Error handlers
├── utils/              # Utility modules
│   └── content.py      # Mentions, hashtags parsing
└── templates/          # 42 HTML templates
```

## Features

### Core Social Features
- 🔐 User authentication with specialty selection
- 📷 Photo & video posts (up to 10 per post)
- 🖼️ Gallery view with lightbox
- 👤 Anonymous posting with specialty tags
- 🎯 Points & gamification system

### Social Interactions
- @mentions - Tag other users (with autocomplete)
- #hashtags - Categorize posts (with autocomplete)
- 🔔 Real-time notifications
- 👍 Like posts
- 💬 Comment on posts
- 🔖 Bookmark posts
- 👥 Follow users

### Community
- 💬 14 investment discussion rooms
- 📊 Expert AMAs with Q&A
- 💰 Vetted investment deal marketplace

### Education & Growth
- 📚 Educational courses
- 📅 Events & conferences
- 🤝 Peer mentorship program
- 🎁 Referral rewards

### Tools
- 📈 Portfolio tracking & analysis
- 🤖 AI financial assistant
- 🔍 Search (posts, users, hashtags)
- 👑 Premium membership tiers

## New in This Version

### @Mentions
- Type `@` followed by a name to mention someone
- Autocomplete dropdown shows matching users
- Mentioned users receive notifications
- Clickable mentions link to user profiles

### #Hashtags
- Type `#` followed by a topic
- Autocomplete shows existing hashtags
- Clickable hashtags show all related posts
- Trending hashtags in sidebar

### Notifications
- Bell icon in navbar with unread count
- Notification types: mentions, likes, comments, follows
- Mark as read / mark all read
- Click to navigate to relevant content

## Optional: Enable AI
Set `ANTHROPIC_API_KEY` environment variable for full AI capabilities.
