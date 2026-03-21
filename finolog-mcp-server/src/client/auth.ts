/**
 * Авторизация для Finolog API
 */

import { config } from '../config/config.js';

export function getAuthHeaders(): Record<string, string> {
  return {
    'Api-Token': config.apiToken,
    'Content-Type': 'application/json',
  };
}

export function validateToken(): void {
  const token = config.apiToken;
  if (!token || token.trim().length === 0) {
    throw new Error(
      'Invalid Finolog API token. Please set FINOLOG_API_TOKEN environment variable.'
    );
  }
}
