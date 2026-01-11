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

## Push Notifications

MedInvest supports Web Push notifications for instant alerts.

### Features
- **Real-time alerts** for mentions, likes, comments, follows
- **AMA reminders** before events start
- **Deal alerts** for new investment opportunities
- **Quiet hours** to pause notifications at night
- **Per-device management** - enable on multiple devices
- **Granular control** - choose which notification types to receive

### Setup (Production)

1. **Generate VAPID keys:**
```bash
npx web-push generate-vapid-keys
# Or with Python:
# python -c "from py_vapid import Vapid; v=Vapid(); v.generate_keys(); print(v.public_key, v.private_key)"
```

2. **Set environment variables:**
```bash
export VAPID_PUBLIC_KEY="your-public-key"
export VAPID_PRIVATE_KEY="your-private-key"
```

3. **For email notifications**, configure SMTP settings (optional).

### How It Works

1. User visits site → Service Worker registers
2. After 30 seconds → Push permission prompt appears
3. User clicks "Enable" → Browser generates subscription
4. Subscription saved to server
5. When notification triggers → Server sends push via Web Push API
6. Service Worker receives → Shows native notification
7. User clicks notification → Opens relevant page

### Notification Types

| Type | Push | Email | Description |
|------|------|-------|-------------|
| Mentions | ✅ | ✅ | When @mentioned |
| Likes | ✅ | ❌ | When post liked |
| Comments | ✅ | ✅ | New comments |
| Follows | ✅ | ✅ | New followers |
| AMA Reminders | ✅ | ✅ | Upcoming events |
| Deal Alerts | ✅ | ✅ | New opportunities |
| Weekly Digest | ❌ | ✅ | Summary email |

### Files

```
routes/push.py           # Push subscription & delivery
static/sw.js             # Service Worker
static/manifest.json     # PWA manifest
static/icons/            # App icons
templates/push/preferences.html
```

## Feed Algorithm

MedInvest uses a custom algorithm optimized for professional investment discussions:

### Formula
```
SCORE = (Engagement × Quality × Author Trust) × Time Decay + Personalization
```

### Components

| Component | Description | Multiplier |
|-----------|-------------|------------|
| **Engagement** | Likes (1x), Comments (3x), Bookmarks (5x) | 0-100+ |
| **Quality** | Long content (+0.3), Media (+0.1), Hashtags (+0.1), Discussion ratio (+0.3) | 1.0-2.0x |
| **Author Trust** | Verified (1.5x), Premium (1.2x), Level 10+ (1.3x), Level 20+ (1.5x) | 1.0-3.0x |
| **Time Decay** | 48-hour half-life (vs 6hr on typical social media) | 0.05-1.0x |
| **Personalization** | Same specialty (+20), Following (+15), Similar hashtags (+10) | 0-50 |

### Key Differences from Facebook/Instagram
- **Quality over virality**: Thoughtful, long-form posts rank higher
- **Expertise matters**: Verified physicians get boosted
- **Longer relevance**: Investment advice stays in feed longer (48hr half-life vs 6hr)
- **Specialty matching**: Posts from your specialty appear more often
- **Discussion valued**: Comments weighted 3x more than likes

### Feed Styles
Users can choose between:
- **For You** (algorithmic) - Personalized based on interests
- **Recent** (chronological) - Newest posts first  
- **Following** - Only posts from followed users

## Background Jobs

The algorithm uses pre-calculated scores for performance. Run jobs with:

```bash
# Manual execution
python jobs.py update_scores      # Every 15 min
python jobs.py snapshot_engagement # Every hour
python jobs.py update_trending    # Every hour
python jobs.py decay_interests    # Daily

# Or run all at once
python jobs.py run_all

# Or start scheduler (requires APScheduler)
python jobs.py start_scheduler
```

### Job Schedule
| Job | Frequency | Description |
|-----|-----------|-------------|
| update_scores | 15 min | Recalculate post scores |
| snapshot_engagement | 1 hour | Track engagement velocity |
| update_trending | 1 hour | Update trending hashtags |
| decay_interests | Daily | Decay user interest scores |
| cleanup | Weekly | Remove old data |
