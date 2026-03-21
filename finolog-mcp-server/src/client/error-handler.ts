/**
 * Обработка ошибок Finolog API
 */

import { AxiosError } from 'axios';
import { ApiError, RateLimitError } from '../types/common.js';
import { logger, logError } from '../utils/logger.js';

export function handleApiError(error: unknown): never {
  if (error instanceof AxiosError) {
    const statusCode = error.response?.status || 500;
    const errorData = error.response?.data;

    logError(error, {
      url: error.config?.url,
      method: error.config?.method,
      statusCode,
      responseData: errorData,
    });

    if (statusCode === 429) {
      const retryAfter = parseInt(error.response?.headers['retry-after'] || '60', 10);
      throw new RateLimitError('Rate limit exceeded.', retryAfter * 1000);
    }

    if (statusCode === 401 || statusCode === 403) {
      throw new ApiError('Authentication failed. Check your Api-Token.', statusCode, 'AUTH_ERROR', errorData);
    }

    if (statusCode === 404) {
      throw new ApiError('Resource not found.', statusCode, 'NOT_FOUND', errorData);
    }

    if (statusCode === 400) {
      const message = errorData?.message || 'Invalid request parameters.';
      throw new ApiError(message, statusCode, 'BAD_REQUEST', errorData);
    }

    if (statusCode >= 500) {
      throw new ApiError('Finolog API server error.', statusCode, 'SERVER_ERROR', errorData);
    }

    const message = errorData?.message || error.message || 'API request failed';
    throw new ApiError(message, statusCode, 'API_ERROR', errorData);
  }

  if (error instanceof Error) {
    logError(error);
    if (error.message.includes('ECONNREFUSED')) {
      throw new ApiError('Cannot connect to Finolog API.', 0, 'NETWORK_ERROR');
    }
    if (error.message.includes('timeout')) {
      throw new ApiError('Request timeout.', 0, 'TIMEOUT_ERROR');
    }
    throw new ApiError(error.message, 500, 'UNKNOWN_ERROR');
  }

  logger.error('Unknown error type', { error });
  throw new ApiError('An unknown error occurred', 500, 'UNKNOWN_ERROR', error);
}

export function isRetryableError(error: ApiError): boolean {
  if (error instanceof RateLimitError) return true;
  if (error.statusCode >= 500) return true;
  if (error.code === 'NETWORK_ERROR' || error.code === 'TIMEOUT_ERROR') return true;
  return false;
}

export function getRetryDelay(attempt: number): number {
  const baseDelay = 1000;
  const maxDelay = 30000;
  const delay = Math.min(baseDelay * Math.pow(2, attempt), maxDelay);
  const jitter = delay * 0.1 * Math.random();
  return delay + jitter;
}
