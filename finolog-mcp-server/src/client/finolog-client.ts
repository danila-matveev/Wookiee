/**
 * Базовый HTTP клиент для Finolog API
 */

import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios';
import { config } from '../config/config.js';
import { getAuthHeaders, validateToken } from './auth.js';
import { globalRateLimiter } from './rate-limiter.js';
import { handleApiError, isRetryableError, getRetryDelay } from './error-handler.js';
import { logger, logRequest, logResponse } from '../utils/logger.js';
import { ApiError } from '../types/common.js';

export class FinologClient {
  private axiosInstance: AxiosInstance;
  private readonly maxRetries: number;

  constructor() {
    validateToken();
    this.maxRetries = config.retry.maxRetries;

    this.axiosInstance = axios.create({
      baseURL: config.apiBaseUrl,
      timeout: config.timeout.default,
      headers: getAuthHeaders(),
    });

    this.setupInterceptors();
  }

  private setupInterceptors(): void {
    this.axiosInstance.interceptors.request.use(
      (cfg) => {
        logRequest(cfg.method?.toUpperCase() || 'GET', cfg.url || '', cfg.data);
        return cfg;
      },
      (error) => Promise.reject(error)
    );

    this.axiosInstance.interceptors.response.use(
      (response) => {
        logResponse(
          response.config.method?.toUpperCase() || 'GET',
          response.config.url || '',
          response.status,
          response.data
        );
        return response;
      },
      (error) => Promise.reject(error)
    );
  }

  private async executeWithRetry<T>(
    requestFn: () => Promise<AxiosResponse<T>>,
    attempt = 0
  ): Promise<T> {
    try {
      const response = await globalRateLimiter.execute(requestFn);
      return response.data;
    } catch (error) {
      const apiError = this.convertToApiError(error);
      if (attempt < this.maxRetries && isRetryableError(apiError)) {
        const delay = getRetryDelay(attempt);
        logger.warn('Retrying request', { attempt: attempt + 1, maxRetries: this.maxRetries, delay });
        await new Promise((resolve) => setTimeout(resolve, delay));
        return this.executeWithRetry(requestFn, attempt + 1);
      }
      throw apiError;
    }
  }

  private convertToApiError(error: unknown): ApiError {
    try {
      handleApiError(error);
    } catch (e) {
      if (e instanceof ApiError) return e;
      throw e;
    }
    throw new ApiError('Unknown error', 500, 'UNKNOWN_ERROR');
  }

  async get<T = unknown>(url: string, params?: unknown): Promise<T> {
    return this.executeWithRetry(() => this.axiosInstance.get<T>(url, { params }));
  }

  async post<T = unknown>(url: string, data?: unknown, cfg?: AxiosRequestConfig): Promise<T> {
    return this.executeWithRetry(() => this.axiosInstance.post<T>(url, data, cfg));
  }

  async put<T = unknown>(url: string, data?: unknown): Promise<T> {
    return this.executeWithRetry(() => this.axiosInstance.put<T>(url, data));
  }

  async delete<T = unknown>(url: string, params?: unknown): Promise<T> {
    return this.executeWithRetry(() => this.axiosInstance.delete<T>(url, { params }));
  }
}

export const finologClient = new FinologClient();
