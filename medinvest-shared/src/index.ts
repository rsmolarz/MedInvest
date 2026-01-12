/**
 * @medinvest/shared
 * 
 * Shared code for MedInvest web and mobile applications.
 * 
 * Usage in Web:
 * ```typescript
 * import { User, Post, loginSchema, formatRelativeTime } from '@medinvest/shared';
 * ```
 * 
 * Usage in Mobile:
 * ```typescript
 * import { User, Post, loginSchema, formatRelativeTime } from '@medinvest/shared';
 * ```
 * 
 * Or import specific modules:
 * ```typescript
 * import { User, Post } from '@medinvest/shared/types';
 * import { loginSchema } from '@medinvest/shared/validators';
 * import { formatRelativeTime } from '@medinvest/shared/utils';
 * import { ApiClient } from '@medinvest/shared/api';
 * import { LIMITS, ERROR_CODES } from '@medinvest/shared/constants';
 * ```
 */

// Types
export * from './types';

// Validators
export * from './validators';

// Utilities
export * from './utils';

// API Client
export * from './api';

// Constants
export * from './constants';
