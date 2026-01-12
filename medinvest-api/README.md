# MedInvest API

Production-ready backend API for the MedInvest platform.

## Tech Stack

- **Runtime**: Node.js 18+
- **Framework**: Express.js
- **Database**: PostgreSQL + Prisma ORM
- **Authentication**: JWT (Access + Refresh tokens)
- **Real-time**: Socket.IO
- **Email**: Nodemailer
- **File Storage**: Local / AWS S3
- **Payments**: Stripe

## Quick Start

### 1. Install Dependencies

```bash
npm install
```

### 2. Set Up Environment

```bash
cp .env.example .env
# Edit .env with your configuration
```

### 3. Set Up Database

```bash
# Create PostgreSQL database
createdb medinvest

# Generate Prisma client
npm run db:generate

# Run migrations
npm run db:push

# Seed initial data (optional)
npm run db:seed
```

### 4. Start Development Server

```bash
npm run dev
```

Server runs at `http://localhost:3000`

## API Endpoints

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/auth/register | Register new user |
| POST | /api/v1/auth/login | Login |
| POST | /api/v1/auth/logout | Logout |
| POST | /api/v1/auth/refresh | Refresh access token |
| POST | /api/v1/auth/forgot-password | Request password reset |
| POST | /api/v1/auth/reset-password | Reset password |
| POST | /api/v1/auth/verify-email | Verify email |
| GET | /api/v1/auth/me | Get current user |

### Users

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/users/me | Get current user profile |
| PUT | /api/v1/users/me | Update profile |
| PUT | /api/v1/users/me/password | Change password |
| GET | /api/v1/users/:id | Get user by ID |
| GET | /api/v1/users/:id/posts | Get user's posts |
| POST | /api/v1/users/:id/follow | Follow user |
| DELETE | /api/v1/users/:id/follow | Unfollow user |
| GET | /api/v1/users/:id/followers | Get followers |
| GET | /api/v1/users/:id/following | Get following |
| POST | /api/v1/users/:id/block | Block user |
| POST | /api/v1/users/:id/mute | Mute user |

### Posts

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/posts/feed | Get feed |
| GET | /api/v1/posts/bookmarks | Get bookmarks |
| GET | /api/v1/posts/:id | Get post |
| POST | /api/v1/posts | Create post |
| PUT | /api/v1/posts/:id | Update post |
| DELETE | /api/v1/posts/:id | Delete post |
| POST | /api/v1/posts/:id/like | Like post |
| POST | /api/v1/posts/:id/react | React to post |
| POST | /api/v1/posts/:id/bookmark | Bookmark post |
| POST | /api/v1/posts/:id/pin | Pin post |
| GET | /api/v1/posts/:id/comments | Get comments |
| POST | /api/v1/posts/:id/comments | Create comment |
| POST | /api/v1/posts/:id/polls/:pollId/vote | Vote on poll |

### Rooms

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/rooms | Get all rooms |
| GET | /api/v1/rooms/joined | Get joined rooms |
| GET | /api/v1/rooms/:id | Get room |
| GET | /api/v1/rooms/:id/posts | Get room posts |
| POST | /api/v1/rooms/:id/join | Join room |
| DELETE | /api/v1/rooms/:id/join | Leave room |

### Messages

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/conversations | Get conversations |
| POST | /api/v1/conversations | Create conversation |
| GET | /api/v1/conversations/:id | Get conversation |
| GET | /api/v1/conversations/:id/messages | Get messages |
| POST | /api/v1/conversations/:id/messages | Send message |
| POST | /api/v1/conversations/:id/read | Mark as read |

### Notifications

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/notifications | Get notifications |
| GET | /api/v1/notifications/unread-count | Get unread count |
| POST | /api/v1/notifications/:id/read | Mark as read |
| POST | /api/v1/notifications/read-all | Mark all read |

### Search

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/search | Search |
| GET | /api/v1/search/trending | Get trending topics |
| GET | /api/v1/search/autocomplete | Autocomplete |

### Deals

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/deals | Get deals |
| GET | /api/v1/deals/:id | Get deal |
| POST | /api/v1/deals/:id/watch | Watch deal |
| POST | /api/v1/deals/:id/interest | Express interest |

### Settings

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/settings/notifications | Get notification settings |
| PUT | /api/v1/settings/notifications | Update notification settings |
| GET | /api/v1/settings/content | Get content preferences |
| PUT | /api/v1/settings/content | Update content preferences |
| GET | /api/v1/settings/privacy | Get privacy settings |
| PUT | /api/v1/settings/privacy | Update privacy settings |

### Account

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/account/export | Request data export |
| GET | /api/v1/account/export/:id/status | Get export status |
| DELETE | /api/v1/account | Delete account |

## WebSocket Events

### Client → Server

| Event | Payload | Description |
|-------|---------|-------------|
| join_conversation | conversationId | Join conversation room |
| leave_conversation | conversationId | Leave conversation room |
| typing_start | conversationId | Started typing |
| typing_stop | conversationId | Stopped typing |
| mark_read | { conversationId, messageId } | Mark message as read |

### Server → Client

| Event | Payload | Description |
|-------|---------|-------------|
| message | Message | New message |
| typing | { conversation_id, user_id, is_typing } | Typing indicator |
| message_read | { conversation_id, message_id, user_id } | Read receipt |
| notification | Notification | New notification |
| user_online | { user_id } | User came online |
| user_offline | { user_id } | User went offline |

## Database Schema

Key models:
- **User** - User accounts
- **Post** - Posts with content, images, video, polls
- **Comment** - Threaded comments
- **Room** - Specialty rooms
- **Message** - Direct messages
- **Notification** - User notifications
- **Deal** - Investment deals
- **Follow/Block/Mute** - Social relationships

See `prisma/schema.prisma` for full schema.

## Deployment

### Railway

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Create project
railway init

# Add PostgreSQL
railway add --plugin postgresql

# Deploy
railway up
```

### Render

1. Create new Web Service
2. Connect GitHub repo
3. Set environment variables
4. Add PostgreSQL database
5. Deploy

### Docker

```dockerfile
FROM node:18-alpine

WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
RUN npm run build
RUN npx prisma generate

EXPOSE 3000
CMD ["npm", "start"]
```

## Project Structure

```
medinvest-api/
├── prisma/
│   └── schema.prisma      # Database schema
├── src/
│   ├── config/            # Configuration
│   │   ├── index.ts
│   │   └── database.ts
│   ├── controllers/       # Route handlers
│   │   ├── auth.ts
│   │   ├── users.ts
│   │   ├── posts.ts
│   │   └── ...
│   ├── middleware/        # Express middleware
│   │   ├── auth.ts
│   │   ├── error.ts
│   │   └── validate.ts
│   ├── routes/           # Route definitions
│   │   ├── index.ts
│   │   ├── auth.ts
│   │   └── ...
│   ├── services/         # Business logic
│   │   ├── email.ts
│   │   └── ...
│   ├── utils/            # Utilities
│   │   ├── jwt.ts
│   │   ├── password.ts
│   │   └── logger.ts
│   ├── websocket/        # WebSocket setup
│   │   └── index.ts
│   └── index.ts          # Entry point
├── .env.example
├── package.json
├── tsconfig.json
└── README.md
```

## Scripts

```bash
npm run dev          # Start development server
npm run build        # Build for production
npm run start        # Start production server
npm run db:generate  # Generate Prisma client
npm run db:push      # Push schema to database
npm run db:migrate   # Run migrations
npm run db:seed      # Seed database
npm run db:studio    # Open Prisma Studio
npm run lint         # Lint code
npm run typecheck    # Type check
```

## License

MIT
