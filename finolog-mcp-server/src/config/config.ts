/**
 * Конфигурация приложения
 */

import { env } from './env.js';

export const FINOLOG_API_BASE_URL = 'https://api.finolog.ru';

export const RATE_LIMIT_CONFIG = {
  maxRequests: 60,
  windowMs: 60000,
  retryAfter: 5000,
};

export const RETRY_CONFIG = {
  maxRetries: 3,
  initialDelay: 1000,
  maxDelay: 10000,
  backoffMultiplier: 2,
};

export const TIMEOUT_CONFIG = {
  default: 30000,
  upload: 120000,
};

export const config = {
  apiToken: env.FINOLOG_API_TOKEN,
  nodeEnv: env.NODE_ENV,
  logLevel: env.LOG_LEVEL,
  apiBaseUrl: FINOLOG_API_BASE_URL,
  rateLimit: RATE_LIMIT_CONFIG,
  retry: RETRY_CONFIG,
  timeout: TIMEOUT_CONFIG,
} as const;
