/**
 * Rate limiter для Finolog API
 */

import { config } from '../config/config.js';
import { logger } from '../utils/logger.js';

export class RateLimiter {
  private requests: number[] = [];
  private readonly maxRequests: number;
  private readonly windowMs: number;

  constructor(maxRequests?: number, windowMs?: number) {
    this.maxRequests = maxRequests || config.rateLimit.maxRequests;
    this.windowMs = windowMs || config.rateLimit.windowMs;
  }

  canMakeRequest(): boolean {
    const now = Date.now();
    this.requests = this.requests.filter((t) => now - t < this.windowMs);
    return this.requests.length < this.maxRequests;
  }

  recordRequest(): void {
    this.requests.push(Date.now());
  }

  getTimeUntilNextSlot(): number {
    if (this.canMakeRequest()) return 0;
    const now = Date.now();
    const oldestRequest = this.requests[0];
    return this.windowMs - (now - oldestRequest);
  }

  async waitForSlot(): Promise<void> {
    while (!this.canMakeRequest()) {
      const waitTime = this.getTimeUntilNextSlot();
      logger.warn('Rate limit reached, waiting', { waitTime });
      await new Promise((resolve) => setTimeout(resolve, waitTime + 100));
    }
  }

  async execute<T>(fn: () => Promise<T>): Promise<T> {
    await this.waitForSlot();
    this.recordRequest();
    return fn();
  }
}

export const globalRateLimiter = new RateLimiter();
