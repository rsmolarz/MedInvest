# @medinvest/shared

Shared types, validators, utilities, and API client for MedInvest web and mobile applications.

## Installation

### Option 1: Copy to Both Projects (Simplest)

1. Copy the `medinvest-shared` folder to both your web and mobile projects
2. Install dependencies in each:

```bash
cd medinvest-shared
npm install
npm run build
```

3. Reference it in your project's `package.json`:

**Web (package.json):**
```json
{
  "dependencies": {
    "@medinvest/shared": "file:../medinvest-shared"
  }
}
```

**Mobile (package.json):**
```json
{
  "dependencies": {
    "@medinvest/shared": "file:../medinvest-shared"
  }
}
```

### Option 2: Monorepo with Workspaces

1. Create a monorepo structure:

```
medinvest/
├── apps/
│   ├── web/
│   └── mobile/
├── packages/
│   └── shared/          <- Put this package here
├── package.json
└── pnpm-workspace.yaml
```

2. Configure workspace in root `package.json`:

```json
{
  "name": "medinvest",
  "private": true,
  "workspaces": ["apps/*", "packages/*"]
}
```

3. Or with pnpm (`pnpm-workspace.yaml`):

```yaml
packages:
  - "apps/*"
  - "packages/*"
```

### Option 3: Publish to npm (Private Registry)

```bash
# Build
npm run build

# Publish to your private registry
npm publish --registry https://your-registry.com
```

## Usage

### Import Everything

```typescript
import { 
  // Types
  User, 
  Post, 
  Message,
  
  // Validators
  loginSchema,
  createPostSchema,
  
  // Utils
  formatRelativeTime,
  formatCompactNumber,
  
  // API Client
  ApiClient,
  createApiClient,
  
  // Constants
  LIMITS,
  ERROR_CODES,
} from '@medinvest/shared';
```

### Import Specific Modules

```typescript
// Types only
import { User, Post, Comment } from '@medinvest/shared/types';

// Validators only
import { loginSchema, registerSchema } from '@medinvest/shared/validators';

// Utils only
import { formatRelativeTime, extractMentions } from '@medinvest/shared/utils';

// API client only
import { ApiClient, createApiClient } from '@medinvest/shared/api';

// Constants only
import { LIMITS, STORAGE_KEYS } from '@medinvest/shared/constants';
```

## API Client Setup

### Web Setup

```typescript
// lib/api.ts
import { createApiClient } from '@medinvest/shared/api';

export const api = createApiClient({
  baseUrl: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3000/api/v1',
  
  getToken: async () => {
    return localStorage.getItem('auth_token');
  },
  
  onUnauthorized: () => {
    localStorage.removeItem('auth_token');
    window.location.href = '/login';
  },
  
  onError: (error) => {
    console.error('API Error:', error);
    // Show toast notification
  },
});

// Usage
const user = await api.getCurrentUser();
const feed = await api.getFeed(1, 20);
await api.createPost({ content: 'Hello world!' });
```

### Mobile Setup

```typescript
// lib/api.ts
import { createApiClient } from '@medinvest/shared/api';
import * as SecureStore from 'expo-secure-store';
import Constants from 'expo-constants';

export const api = createApiClient({
  baseUrl: Constants.expoConfig?.extra?.apiUrl || 'http://localhost:3000/api/v1',
  
  getToken: async () => {
    return await SecureStore.getItemAsync('auth_token');
  },
  
  onUnauthorized: () => {
    SecureStore.deleteItemAsync('auth_token');
    // Navigate to login screen
  },
  
  onError: (error) => {
    console.error('API Error:', error);
    // Show alert
  },
});
```

## Validation Examples

```typescript
import { loginSchema, createPostSchema, type LoginInput } from '@medinvest/shared';

// Form validation
function handleLogin(formData: unknown) {
  try {
    const validData = loginSchema.parse(formData);
    // validData is typed as LoginInput
    await api.login(validData);
  } catch (error) {
    if (error instanceof z.ZodError) {
      // Handle validation errors
      console.log(error.errors);
    }
  }
}

// React Hook Form integration
import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';

const form = useForm<LoginInput>({
  resolver: zodResolver(loginSchema),
});
```

## Utility Examples

```typescript
import {
  formatRelativeTime,
  formatCompactNumber,
  formatCurrency,
  extractMentions,
  extractHashtags,
  truncate,
  debounce,
} from '@medinvest/shared/utils';

// Time formatting
formatRelativeTime('2024-01-15T10:30:00Z'); // "2h"
formatRelativeTime('2024-01-10T10:30:00Z'); // "5d"

// Number formatting
formatCompactNumber(1234);     // "1.2K"
formatCompactNumber(1234567);  // "1.2M"

// Currency formatting
formatCurrency(50000);                    // "$50,000"
formatCurrency(1500000, 'USD', true);     // "$1.5M"

// Content parsing
extractMentions('Hello @john and @jane'); // ["john", "jane"]
extractHashtags('Check out #react and #typescript'); // ["react", "typescript"]

// String utilities
truncate('This is a long string', 10); // "This is..."

// Debounce (for search)
const debouncedSearch = debounce((query: string) => {
  api.search(query);
}, 300);
```

## Constants

```typescript
import { LIMITS, ERROR_CODES, STORAGE_KEYS, DEEP_LINKS } from '@medinvest/shared/constants';

// Content limits
if (content.length > LIMITS.POST_CONTENT_MAX) {
  // Show error
}

// Error handling
if (error.code === ERROR_CODES.UNAUTHORIZED) {
  // Redirect to login
}

// Storage keys (consistent across platforms)
await storage.setItem(STORAGE_KEYS.AUTH_TOKEN, token);

// Deep links
Linking.openURL(DEEP_LINKS.POST + '/123');
```

## Types Reference

### User Types
- `User` - Full user object
- `UserProfile` - User with follow status
- `UserPreview` - Minimal user info for lists

### Post Types
- `Post` - Full post object
- `PostCreate` - Creating a post
- `PostUpdate` - Updating a post

### Other Types
- `Comment`, `CommentCreate`
- `Message`, `MessageCreate`
- `Conversation`
- `Notification`
- `Room`
- `Deal`
- `Poll`, `PollCreate`
- `ReactionType`, `ReactionCount`
- `SearchResults`, `SearchFilters`
- `NotificationSettings`
- `ContentPreferences`
- `PrivacySettings`

## Building

```bash
# Install dependencies
npm install

# Build
npm run build

# Watch mode (development)
npm run dev

# Type check
npm run typecheck
```

## Structure

```
medinvest-shared/
├── src/
│   ├── index.ts           # Main entry point
│   ├── types/
│   │   └── index.ts       # All TypeScript types
│   ├── validators/
│   │   └── index.ts       # Zod schemas
│   ├── utils/
│   │   └── index.ts       # Utility functions
│   ├── api/
│   │   └── index.ts       # API client
│   └── constants/
│       └── index.ts       # Constants
├── package.json
├── tsconfig.json
├── tsup.config.ts
└── README.md
```

## License

MIT
