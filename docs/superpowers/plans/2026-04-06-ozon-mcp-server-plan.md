# Ozon MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a complete MCP server covering all ~278 Ozon Seller API methods as MCP tools, in a separate GitHub repository mirroring the finolog-mcp-server architecture.

**Architecture:** TypeScript MCP server with stdio/http transport, Axios HTTP client with retry/rate-limiting, 33 tool category folders each containing individual tool files with definition + handler exports, aggregated through a central registry.

**Tech Stack:** TypeScript 5.7+, Node.js 18+, @modelcontextprotocol/sdk ^1.0.4, Axios ^1.7.9, Zod ^3.24.1, Winston ^3.17.0, dotenv ^16.4.7

**Spec:** `docs/superpowers/specs/2026-04-06-ozon-mcp-server-design.md`

**Reference implementation:** `~/Desktop/Документы/Cursor/finolog-mcp-server/`

---

## Task 1: Initialize Project

**Files:**
- Create: `~/Desktop/Документы/Cursor/ozon-mcp-server/package.json`
- Create: `~/Desktop/Документы/Cursor/ozon-mcp-server/tsconfig.json`
- Create: `~/Desktop/Документы/Cursor/ozon-mcp-server/.gitignore`
- Create: `~/Desktop/Документы/Cursor/ozon-mcp-server/.env.example`
- Create: `~/Desktop/Документы/Cursor/ozon-mcp-server/README.md`

- [ ] **Step 1: Create directory and initialize git**

```bash
cd ~/Desktop/Документы/Cursor
mkdir ozon-mcp-server && cd ozon-mcp-server
git init
```

- [ ] **Step 2: Create package.json**

```json
{
  "name": "ozon-mcp-server",
  "version": "0.1.0",
  "description": "Model Context Protocol server for Ozon Seller API integration",
  "type": "module",
  "main": "dist/index.js",
  "bin": {
    "ozon-mcp": "dist/index.js"
  },
  "scripts": {
    "build": "tsc",
    "dev": "tsc --watch",
    "start": "node dist/index.js",
    "prepare": "npm run build"
  },
  "keywords": [
    "mcp-server",
    "ozon",
    "ozon-seller-api",
    "model-context-protocol",
    "typescript",
    "api-integration"
  ],
  "author": "",
  "license": "MIT",
  "dependencies": {
    "@modelcontextprotocol/sdk": "^1.0.4",
    "axios": "^1.7.9",
    "dotenv": "^16.4.7",
    "winston": "^3.17.0",
    "zod": "^3.24.1"
  },
  "devDependencies": {
    "@types/node": "^22.10.5",
    "typescript": "^5.7.2"
  },
  "engines": {
    "node": ">=18.0.0"
  }
}
```

- [ ] **Step 3: Create tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "Node16",
    "moduleResolution": "Node16",
    "lib": ["ES2022"],
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true,
    "declaration": true,
    "declarationMap": true,
    "sourceMap": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noImplicitReturns": true,
    "noFallthroughCasesInSwitch": true
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules", "dist", "tests"]
}
```

- [ ] **Step 4: Create .gitignore**

```
node_modules/
dist/
logs/
.env
*.log
.DS_Store
```

- [ ] **Step 5: Create .env.example**

```bash
# Required — default Ozon account
OZON_CLIENT_ID=0000000
OZON_API_KEY=00000000-0000-0000-0000-000000000000

# Optional — second account (ООО)
OZON_CLIENT_ID_OOO=0000000
OZON_API_KEY_OOO=00000000-0000-0000-0000-000000000000

# Optional
MCP_TRANSPORT=stdio
MCP_PORT=8082
LOG_LEVEL=info
NODE_ENV=development
```

- [ ] **Step 6: Create .env with real keys**

Copy from Wookiee project's `.env`:
```bash
OZON_CLIENT_ID=1410333
OZON_API_KEY=82ad849b-4cf6-4a15-9151-702787e80764
OZON_CLIENT_ID_OOO=1540263
OZON_API_KEY_OOO=c4a7b511-b3db-41e7-9619-44cf611dcd70
```

- [ ] **Step 7: Install dependencies and commit**

```bash
npm install
git add package.json tsconfig.json .gitignore .env.example README.md
git commit -m "chore: initialize ozon-mcp-server project"
```

---

## Task 2: Core Types

**Files:**
- Create: `src/types/tools.ts`
- Create: `src/types/common.ts`

- [ ] **Step 1: Create src/types/tools.ts**

```typescript
/**
 * Типы для MCP инструментов
 */

export interface ToolParams {
  [key: string]: unknown;
}

export interface ToolResponse {
  content: Array<{
    type: 'text' | 'image' | 'resource';
    text?: string;
    data?: string;
    mimeType?: string;
  }>;
  isError?: boolean;
}

export interface ToolDefinition {
  name: string;
  description: string;
  inputSchema: {
    type: 'object';
    properties: Record<string, unknown>;
    required?: string[];
  };
}

export type ToolHandler = (params: ToolParams) => Promise<ToolResponse>;
```

- [ ] **Step 2: Create src/types/common.ts**

```typescript
/**
 * Общие типы
 */

export class ApiError extends Error {
  constructor(
    message: string,
    public statusCode: number,
    public code?: string,
    public details?: unknown
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export class RateLimitError extends ApiError {
  constructor(
    message: string,
    public retryAfter: number
  ) {
    super(message, 429, 'RATE_LIMIT_EXCEEDED');
    this.name = 'RateLimitError';
  }
}
```

- [ ] **Step 3: Commit**

```bash
git add src/types/
git commit -m "feat: add core type definitions"
```

---

## Task 3: Config & Environment

**Files:**
- Create: `src/config/env.ts`
- Create: `src/config/config.ts`

- [ ] **Step 1: Create src/config/env.ts**

```typescript
/**
 * Валидация переменных окружения
 */

import { z } from 'zod';
import dotenv from 'dotenv';

dotenv.config();

const envSchema = z.object({
  OZON_CLIENT_ID: z.string().min(1, 'OZON_CLIENT_ID is required'),
  OZON_API_KEY: z.string().min(1, 'OZON_API_KEY is required'),
  OZON_CLIENT_ID_OOO: z.string().optional(),
  OZON_API_KEY_OOO: z.string().optional(),
  NODE_ENV: z.enum(['development', 'production', 'test']).default('development'),
  LOG_LEVEL: z.enum(['error', 'warn', 'info', 'debug']).default('info'),
});

export type Env = z.infer<typeof envSchema>;

function validateEnv(): Env {
  try {
    return envSchema.parse({
      OZON_CLIENT_ID: process.env.OZON_CLIENT_ID,
      OZON_API_KEY: process.env.OZON_API_KEY,
      OZON_CLIENT_ID_OOO: process.env.OZON_CLIENT_ID_OOO,
      OZON_API_KEY_OOO: process.env.OZON_API_KEY_OOO,
      NODE_ENV: process.env.NODE_ENV || 'development',
      LOG_LEVEL: process.env.LOG_LEVEL || 'info',
    });
  } catch (error) {
    if (error instanceof z.ZodError) {
      const missingVars = error.errors.map((e) => e.path.join('.')).join(', ');
      throw new Error(
        `Missing or invalid environment variables: ${missingVars}\n` +
        'Please set OZON_CLIENT_ID and OZON_API_KEY environment variables.'
      );
    }
    throw error;
  }
}

export const env = validateEnv();
```

- [ ] **Step 2: Create src/config/config.ts**

```typescript
/**
 * Конфигурация приложения
 */

import { env } from './env.js';

export const OZON_API_BASE_URL = 'https://api-seller.ozon.ru';

export const RATE_LIMIT_CONFIG = {
  maxRequests: 50,
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
  clientId: env.OZON_CLIENT_ID,
  apiKey: env.OZON_API_KEY,
  clientIdOoo: env.OZON_CLIENT_ID_OOO,
  apiKeyOoo: env.OZON_API_KEY_OOO,
  nodeEnv: env.NODE_ENV,
  logLevel: env.LOG_LEVEL,
  apiBaseUrl: OZON_API_BASE_URL,
  rateLimit: RATE_LIMIT_CONFIG,
  retry: RETRY_CONFIG,
  timeout: TIMEOUT_CONFIG,
} as const;
```

- [ ] **Step 3: Commit**

```bash
git add src/config/
git commit -m "feat: add config and environment validation"
```

---

## Task 4: Utils (Logger & Formatter)

**Files:**
- Create: `src/utils/logger.ts`
- Create: `src/utils/formatter.ts`

- [ ] **Step 1: Create src/utils/logger.ts**

```typescript
/**
 * Настройка логирования с использованием Winston
 */

import winston from 'winston';
import { env } from '../config/env.js';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const logFormat = winston.format.combine(
  winston.format.timestamp({ format: 'YYYY-MM-DD HH:mm:ss' }),
  winston.format.errors({ stack: true }),
  winston.format.printf(({ timestamp, level, message, stack, ...meta }) => {
    let log = `[${timestamp}] [${level.toUpperCase()}] ${message}`;
    if (Object.keys(meta).length > 0) {
      log += ` ${JSON.stringify(meta, null, 2)}`;
    }
    if (stack) {
      log += `\n${stack}`;
    }
    return log;
  })
);

const logsDir = path.resolve(__dirname, '../../logs');

export const logger = winston.createLogger({
  level: env.LOG_LEVEL,
  format: logFormat,
  transports: [
    new winston.transports.Console({
      format: winston.format.combine(
        winston.format.colorize(),
        logFormat
      ),
    }),
    new winston.transports.File({
      filename: path.join(logsDir, 'combined.log'),
      maxsize: 5242880,
      maxFiles: 5,
    }),
    new winston.transports.File({
      filename: path.join(logsDir, 'error.log'),
      level: 'error',
      maxsize: 5242880,
      maxFiles: 5,
    }),
  ],
});

export function logRequest(method: string, url: string, data?: unknown) {
  logger.debug('API Request', {
    method,
    url,
    ...(data ? { data: sanitizeData(data) } : {}),
  });
}

export function logResponse(method: string, url: string, status: number, data?: unknown) {
  logger.debug('API Response', {
    method,
    url,
    status,
    ...(data ? { data: sanitizeData(data) } : {}),
  });
}

export function logError(error: Error, context?: Record<string, unknown>) {
  logger.error('Error occurred', {
    message: error.message,
    stack: error.stack,
    ...context,
  });
}

function sanitizeData(data: unknown): unknown {
  if (typeof data !== 'object' || data === null) {
    return data;
  }
  const sanitized = { ...data } as Record<string, unknown>;
  const sensitiveKeys = ['token', 'password', 'apikey', 'api-key', 'authorization', 'secret'];
  for (const key of Object.keys(sanitized)) {
    const lowerKey = key.toLowerCase();
    if (sensitiveKeys.some((sensitive) => lowerKey.includes(sensitive))) {
      sanitized[key] = '***REDACTED***';
    } else if (typeof sanitized[key] === 'object' && sanitized[key] !== null) {
      sanitized[key] = sanitizeData(sanitized[key]);
    }
  }
  return sanitized;
}
```

- [ ] **Step 2: Create src/utils/formatter.ts**

```typescript
/**
 * Утилиты для форматирования данных
 */

export function formatApiResponse<T>(data: T, metadata?: Record<string, unknown>): {
  content: Array<{ type: 'text'; text: string }>;
} {
  const formattedData = {
    data,
    ...(metadata && { metadata }),
  };
  return {
    content: [{ type: 'text', text: JSON.stringify(formattedData, null, 2) }],
  };
}

export function formatError(error: Error | unknown, context?: string): {
  content: Array<{ type: 'text'; text: string }>;
  isError: true;
} {
  const errorMessage = error instanceof Error ? error.message : String(error);
  const formattedError = {
    error: errorMessage,
    ...(context && { context }),
  };
  return {
    content: [{ type: 'text', text: JSON.stringify(formattedError, null, 2) }],
    isError: true,
  };
}
```

- [ ] **Step 3: Commit**

```bash
git add src/utils/
git commit -m "feat: add logger and response formatter utils"
```

---

## Task 5: HTTP Client Layer

**Files:**
- Create: `src/client/auth.ts`
- Create: `src/client/rate-limiter.ts`
- Create: `src/client/error-handler.ts`
- Create: `src/client/ozon-client.ts`

- [ ] **Step 1: Create src/client/auth.ts**

Ozon uses `Client-Id` + `Api-Key` headers (unlike Finolog's single `Api-Token`).

```typescript
/**
 * Авторизация для Ozon Seller API
 */

import { config } from '../config/config.js';

export type AccountType = 'ip' | 'ooo';

export function getAuthHeaders(account: AccountType = 'ip'): Record<string, string> {
  if (account === 'ooo') {
    if (!config.clientIdOoo || !config.apiKeyOoo) {
      throw new Error('OOO account credentials not configured. Set OZON_CLIENT_ID_OOO and OZON_API_KEY_OOO.');
    }
    return {
      'Client-Id': config.clientIdOoo,
      'Api-Key': config.apiKeyOoo,
      'Content-Type': 'application/json',
    };
  }
  return {
    'Client-Id': config.clientId,
    'Api-Key': config.apiKey,
    'Content-Type': 'application/json',
  };
}

export function validateCredentials(): void {
  if (!config.clientId || config.clientId.trim().length === 0) {
    throw new Error('Invalid OZON_CLIENT_ID. Please set OZON_CLIENT_ID environment variable.');
  }
  if (!config.apiKey || config.apiKey.trim().length === 0) {
    throw new Error('Invalid OZON_API_KEY. Please set OZON_API_KEY environment variable.');
  }
}
```

- [ ] **Step 2: Create src/client/rate-limiter.ts**

```typescript
/**
 * Rate limiter для Ozon Seller API
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
```

- [ ] **Step 3: Create src/client/error-handler.ts**

```typescript
/**
 * Обработка ошибок Ozon Seller API
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
      throw new ApiError(
        'Authentication failed. Check Client-Id and Api-Key.',
        statusCode,
        'AUTH_ERROR',
        errorData
      );
    }

    if (statusCode === 404) {
      throw new ApiError('Resource not found.', statusCode, 'NOT_FOUND', errorData);
    }

    if (statusCode === 400) {
      const message = errorData?.message || errorData?.error || 'Invalid request parameters.';
      throw new ApiError(message, statusCode, 'BAD_REQUEST', errorData);
    }

    if (statusCode >= 500) {
      throw new ApiError('Ozon API server error.', statusCode, 'SERVER_ERROR', errorData);
    }

    const message = errorData?.message || error.message || 'API request failed';
    throw new ApiError(message, statusCode, 'API_ERROR', errorData);
  }

  if (error instanceof Error) {
    logError(error);
    if (error.message.includes('ECONNREFUSED')) {
      throw new ApiError('Cannot connect to Ozon API.', 0, 'NETWORK_ERROR');
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
```

- [ ] **Step 4: Create src/client/ozon-client.ts**

All Ozon Seller API endpoints use POST method. The client supports multi-account via `account` parameter.

```typescript
/**
 * Базовый HTTP клиент для Ozon Seller API
 */

import axios, { AxiosInstance, AxiosResponse } from 'axios';
import { config } from '../config/config.js';
import { getAuthHeaders, validateCredentials, AccountType } from './auth.js';
import { globalRateLimiter } from './rate-limiter.js';
import { handleApiError, isRetryableError, getRetryDelay } from './error-handler.js';
import { logger, logRequest, logResponse } from '../utils/logger.js';
import { ApiError } from '../types/common.js';

export class OzonClient {
  private instances: Map<AccountType, AxiosInstance> = new Map();
  private readonly maxRetries: number;

  constructor() {
    validateCredentials();
    this.maxRetries = config.retry.maxRetries;
    this.instances.set('ip', this.createInstance('ip'));
    if (config.clientIdOoo && config.apiKeyOoo) {
      this.instances.set('ooo', this.createInstance('ooo'));
    }
  }

  private createInstance(account: AccountType): AxiosInstance {
    const instance = axios.create({
      baseURL: config.apiBaseUrl,
      timeout: config.timeout.default,
      headers: getAuthHeaders(account),
    });

    instance.interceptors.request.use(
      (cfg) => {
        logRequest('POST', cfg.url || '', cfg.data);
        return cfg;
      },
      (error) => Promise.reject(error)
    );

    instance.interceptors.response.use(
      (response) => {
        logResponse('POST', response.config.url || '', response.status, response.data);
        return response;
      },
      (error) => Promise.reject(error)
    );

    return instance;
  }

  private getInstance(account: AccountType = 'ip'): AxiosInstance {
    const instance = this.instances.get(account);
    if (!instance) {
      throw new Error(`Account "${account}" not configured.`);
    }
    return instance;
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

  async post<T = unknown>(url: string, data?: unknown, account: AccountType = 'ip'): Promise<T> {
    const instance = this.getInstance(account);
    return this.executeWithRetry(() => instance.post<T>(url, data));
  }
}

export const ozonClient = new OzonClient();
```

- [ ] **Step 5: Commit**

```bash
git add src/client/
git commit -m "feat: add Ozon API client with auth, rate limiting, and retry"
```

---

## Task 6: Entry Point (index.ts)

**Files:**
- Create: `src/index.ts`

- [ ] **Step 1: Create src/index.ts**

```typescript
#!/usr/bin/env node

/**
 * Точка входа MCP сервера для Ozon Seller API.
 * Поддерживает два транспорта: stdio (default) и HTTP (MCP_TRANSPORT=http).
 */

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { StreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/streamableHttp.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import { createServer, IncomingMessage, ServerResponse } from 'node:http';

import { allTools, getHandler } from './tools/index.js';
import { logger } from './utils/logger.js';
import { config } from './config/config.js';

function createMcpServer(): Server {
  const server = new Server(
    { name: 'ozon-mcp-server', version: '0.1.0' },
    { capabilities: { tools: {} } }
  );

  server.setRequestHandler(ListToolsRequestSchema, async () => {
    logger.debug('Listing tools', { count: allTools.length });
    return {
      tools: allTools.map((tool) => ({
        name: tool.name,
        description: tool.description,
        inputSchema: tool.inputSchema,
      })),
    };
  });

  server.setRequestHandler(CallToolRequestSchema, async (request: any): Promise<any> => {
    const { name, arguments: args } = request.params;
    logger.info('Tool called', { name, args });

    try {
      const handler = getHandler(name);
      if (!handler) {
        const errorMsg = `Unknown tool: ${name}`;
        logger.error(errorMsg);
        return {
          content: [{ type: 'text' as const, text: JSON.stringify({ error: errorMsg }, null, 2) }],
          isError: true,
        };
      }

      const result = await handler(args || {});
      logger.info('Tool executed successfully', { name });
      return result;
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      logger.error('Tool execution failed', { name, error: errorMsg });
      return {
        content: [{ type: 'text' as const, text: JSON.stringify({ error: errorMsg, tool: name }, null, 2) }],
        isError: true,
      };
    }
  });

  return server;
}

async function startStdio() {
  const server = createMcpServer();
  const transport = new StdioServerTransport();
  await server.connect(transport);

  logger.info('Ozon MCP Server started (stdio)', { toolsCount: allTools.length });

  const signals: NodeJS.Signals[] = ['SIGINT', 'SIGTERM', 'SIGQUIT'];
  signals.forEach((signal) => {
    process.on(signal, async () => {
      logger.info('Shutting down', { signal });
      await server.close();
      process.exit(0);
    });
  });
}

async function startHttp() {
  const port = parseInt(process.env['MCP_PORT'] || '8082', 10);

  const httpServer = createServer(async (req: IncomingMessage, res: ServerResponse) => {
    const url = req.url || '/';

    if (url === '/health' && req.method === 'GET') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'ok', service: 'ozon-mcp' }));
      return;
    }

    if (url === '/mcp' || url === '/mcp/') {
      const server = createMcpServer();
      const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: undefined });
      await server.connect(transport);
      await transport.handleRequest(req, res);
      return;
    }

    res.writeHead(404);
    res.end('Not Found');
  });

  httpServer.listen(port, '0.0.0.0', () => {
    logger.info(`Ozon MCP Server started (HTTP) on port ${port}`, { toolsCount: allTools.length });
  });

  const signals: NodeJS.Signals[] = ['SIGINT', 'SIGTERM', 'SIGQUIT'];
  signals.forEach((signal) => {
    process.on(signal, () => {
      logger.info('Shutting down', { signal });
      httpServer.close();
      process.exit(0);
    });
  });
}

async function main() {
  try {
    logger.info('Starting Ozon MCP Server', {
      version: '0.1.0',
      nodeEnv: config.nodeEnv,
      transport: process.env['MCP_TRANSPORT'] || 'stdio',
    });

    if (process.env['MCP_TRANSPORT'] === 'http') {
      await startHttp();
    } else {
      await startStdio();
    }
  } catch (error) {
    logger.error('Failed to start MCP Server', { error });
    process.exit(1);
  }
}

main().catch((error) => {
  logger.error('Unhandled error in main', { error });
  process.exit(1);
});
```

- [ ] **Step 2: Commit**

```bash
git add src/index.ts
git commit -m "feat: add MCP server entry point with stdio/http transport"
```

---

## Task 7: API Research — Complete Endpoint Catalog

**Agent:** Agent 1 (Researcher)

This task produces a comprehensive catalog of all Ozon Seller API endpoints by parsing the official documentation. The output is used by Task 8+ to implement tools.

- [ ] **Step 1: Research all Ozon Seller API documentation pages**

Use WebFetch on these documentation pages to extract all endpoints:
- `https://docs.ozon.ru/api/seller/` — main index
- Each category page linked from the index

For each endpoint, capture:
- HTTP path (e.g., `/v2/product/list`)
- Description (Russian)
- Request parameters with types
- Required parameters
- Response structure summary

- [ ] **Step 2: Write docs/api-catalog.json**

Output a JSON file with this structure:

```json
{
  "categories": [
    {
      "name": "product",
      "description": "Product management",
      "tools": [
        {
          "name": "ozon_product_list",
          "endpoint": "/v2/product/list",
          "description": "Получить список товаров с пагинацией",
          "inputSchema": {
            "type": "object",
            "properties": {
              "filter": { "type": "object", "description": "Фильтры" },
              "last_id": { "type": "string", "description": "ID для пагинации" },
              "limit": { "type": "number", "description": "Кол-во на стр (max 1000)", "default": 100 }
            }
          }
        }
      ]
    }
  ]
}
```

- [ ] **Step 3: Commit catalog**

```bash
git add docs/api-catalog.json
git commit -m "docs: add complete Ozon Seller API endpoint catalog"
```

---

## Task 8: Tool Implementation — Wave 1 (Core Business)

**Agent:** Agent 2 (Builder)
**Categories:** product (23), fbs (22), fbo (13), finance (10), prices-stocks (9), analytics (2), warehouse (2)
**Total:** ~81 tools

Each category follows this exact pattern. Here is the full template using `product` as example:

### Pattern: Category Index File

```typescript
// src/tools/product/index.ts
import { ToolDefinition, ToolHandler } from '../../types/tools.js';

import { productListTool, productListHandler } from './list.js';
import { productInfoTool, productInfoHandler } from './info.js';
// ... import all tools in this category

export const productTools: ToolDefinition[] = [
  productListTool,
  productInfoTool,
  // ... all tools
];

export const productHandlers: Record<string, ToolHandler> = {
  [productListTool.name]: productListHandler,
  [productInfoTool.name]: productInfoHandler,
  // ... all handlers
};
```

### Pattern: Individual Tool File

```typescript
// src/tools/product/list.ts
import { ozonClient } from '../../client/ozon-client.js';
import { ToolDefinition, ToolHandler } from '../../types/tools.js';
import { formatApiResponse, formatError } from '../../utils/formatter.js';
import { logger } from '../../utils/logger.js';

export const productListTool: ToolDefinition = {
  name: 'ozon_product_list',
  description: 'Получить список товаров. Возвращает product_id, offer_id и базовую информацию. Поддерживает фильтрацию по видимости и пагинацию.',
  inputSchema: {
    type: 'object',
    properties: {
      filter: {
        type: 'object',
        description: 'Фильтры для товаров',
        properties: {
          offer_id: { type: 'array', items: { type: 'string' }, description: 'Фильтр по артикулу продавца' },
          product_id: { type: 'array', items: { type: 'number' }, description: 'Фильтр по ID товара' },
          visibility: {
            type: 'string',
            enum: ['ALL', 'VISIBLE', 'INVISIBLE', 'EMPTY_STOCK', 'NOT_MODERATED', 'MODERATED', 'DISABLED', 'STATE_FAILED', 'READY_TO_SUPPLY', 'VALIDATION_STATE_PENDING', 'VALIDATION_STATE_FAIL', 'VALIDATION_STATE_SUCCESS', 'TO_SUPPLY', 'IN_SALE', 'REMOVED_FROM_SALE', 'BAN_NOT_SKU', 'ARCHIVED', 'OVERPRICED'],
            description: 'Фильтр по видимости товара'
          }
        }
      },
      last_id: { type: 'string', description: 'ID последнего товара для пагинации' },
      limit: { type: 'number', description: 'Количество товаров (макс 1000, по умолчанию 100)' },
      account: { type: 'string', enum: ['ip', 'ooo'], description: 'Аккаунт (по умолчанию ip)' }
    }
  }
};

export const productListHandler: ToolHandler = async (params) => {
  try {
    const { account, ...body } = params as any;
    const response = await ozonClient.post('/v2/product/list', body, account);
    return formatApiResponse(response);
  } catch (error) {
    logger.error('Failed to list products', { error });
    return formatError(error, 'ozon_product_list');
  }
};
```

- [ ] **Step 1: Create all tool files for `product/` category (~23 tools)**

Using `docs/api-catalog.json` as reference, create one file per endpoint. Key endpoints:
- `list.ts` → POST `/v2/product/list`
- `info.ts` → POST `/v2/product/info`
- `info-list.ts` → POST `/v2/product/info/list`
- `import.ts` → POST `/v1/product/import`
- `update.ts` → POST `/v1/product/update`
- `archive.ts` → POST `/v1/product/archive`
- `unarchive.ts` → POST `/v1/product/unarchive`
- `delete.ts` → POST `/v1/product/delete`
- `attributes.ts` → POST `/v3/products/info/attributes`
- `import-by-sku.ts` → POST `/v1/product/import-by-sku`
- `pictures-import.ts` → POST `/v1/product/pictures/import`
- `pictures-info.ts` → POST `/v1/product/pictures/info`
- `geo-restrictions.ts` → POST `/v1/product/geo-restrictions-catalog-by-filter`
- `description.ts` → POST `/v1/product/update/description`
- `update-offer-id.ts` → POST `/v1/product/update/offer-id`
- `info-discounted.ts` → POST `/v1/product/info/discounted`
- `info-stocks.ts` → POST `/v3/product/info/stocks`
- `info-prices.ts` → POST `/v4/product/info/prices`
- `rating-by-sku.ts` → POST `/v1/product/rating-by-sku`
- `related-sku-get.ts` → POST `/v1/product/related-sku/get`
- `upload-digital-codes.ts` → POST `/v1/product/upload_digital_codes`
- `info-subscription.ts` → POST `/v1/product/info/subscription`
- `pictures-copy.ts` → POST `/v1/product/pictures/copy`

- [ ] **Step 2: Create `product/index.ts`** aggregating all tools and handlers

- [ ] **Step 3: Repeat for `fbs/` (~22 tools)** — FBS posting list/get/ship, cancel, labels, tracking, etc.

- [ ] **Step 4: Repeat for `fbo/` (~13 tools)** — FBO posting list/get, shipment info

- [ ] **Step 5: Repeat for `finance/` (~10 tools)** — transactions, realization, totals

- [ ] **Step 6: Repeat for `prices-stocks/` (~9 tools)** — stock update, price import

- [ ] **Step 7: Repeat for `analytics/` (~2 tools)** — analytics data

- [ ] **Step 8: Repeat for `warehouse/` (~2 tools)** — warehouse list

- [ ] **Step 9: Commit Wave 1**

```bash
git add src/tools/product/ src/tools/fbs/ src/tools/fbo/ src/tools/finance/ src/tools/prices-stocks/ src/tools/analytics/ src/tools/warehouse/
git commit -m "feat: add Wave 1 tool categories (product, fbs, fbo, finance, prices-stocks, analytics, warehouse)"
```

---

## Task 9: Tool Implementation — Wave 2 (Orders & Delivery)

**Agent:** Agent 2 (Builder)
**Categories:** fbo-supply (19), delivery-fbs (18), fbs-marks (13), delivery-rfbs (8), pass (7), cancellation (7)
**Total:** ~72 tools

Follow the exact same pattern as Task 8. Each category gets its own folder with individual tool files + index.ts.

- [ ] **Step 1: Create `fbo-supply/` (~19 tools)** — supply request CRUD, timeslots
- [ ] **Step 2: Create `delivery-fbs/` (~18 tools)** — delivery methods, tracking number set
- [ ] **Step 3: Create `fbs-marks/` (~13 tools)** — labeling, packaging marks
- [ ] **Step 4: Create `delivery-rfbs/` (~8 tools)** — rFBS delivery
- [ ] **Step 5: Create `pass/` (~7 tools)** — warehouse delivery passes
- [ ] **Step 6: Create `cancellation/` (~7 tools)** — order cancellations

- [ ] **Step 7: Commit Wave 2**

```bash
git add src/tools/fbo-supply/ src/tools/delivery-fbs/ src/tools/fbs-marks/ src/tools/delivery-rfbs/ src/tools/pass/ src/tools/cancellation/
git commit -m "feat: add Wave 2 tool categories (fbo-supply, delivery, marks, cancellation)"
```

---

## Task 10: Tool Implementation — Wave 3 (Returns, Reports & Pricing)

**Agent:** Agent 2 (Builder)
**Categories:** pricing-strategy (12), certification (12), return-fbo (8), return-rfbs (8), report (8), premium (8)
**Total:** ~56 tools

- [ ] **Step 1: Create `pricing-strategy/` (~12 tools)** — strategy CRUD, competitor prices
- [ ] **Step 2: Create `certification/` (~12 tools)** — quality certificates, brand docs
- [ ] **Step 3: Create `return-fbo/` (~8 tools)** — FBO return processing
- [ ] **Step 4: Create `return-rfbs/` (~8 tools)** — rFBS return management
- [ ] **Step 5: Create `report/` (~8 tools)** — report create/status/download
- [ ] **Step 6: Create `premium/` (~8 tools)** — premium seller features

- [ ] **Step 7: Commit Wave 3**

```bash
git add src/tools/pricing-strategy/ src/tools/certification/ src/tools/return-fbo/ src/tools/return-rfbs/ src/tools/report/ src/tools/premium/
git commit -m "feat: add Wave 3 tool categories (pricing, certification, returns, reports, premium)"
```

---

## Task 11: Tool Implementation — Wave 4 (Communication & Misc)

**Agent:** Agent 2 (Builder)
**Categories:** promos (8), chat (8), qa (8), review (7), category (6), beta (9), barcode (5), polygon (4), supplier (4), digital (4), quants (2), rating (2), brand (1), returns (1)
**Total:** ~69 tools

- [ ] **Step 1: Create `promos/` (~8 tools)** — promotions, actions
- [ ] **Step 2: Create `chat/` (~8 tools)** — messages, chat list/history
- [ ] **Step 3: Create `qa/` (~8 tools)** — questions & answers
- [ ] **Step 4: Create `review/` (~7 tools)** — review list/management
- [ ] **Step 5: Create `category/` (~6 tools)** — category tree, attributes, values
- [ ] **Step 6: Create `beta/` (~9 tools)** — experimental endpoints
- [ ] **Step 7: Create `barcode/` (~5 tools)** — barcode generation
- [ ] **Step 8: Create `polygon/` (~4 tools)** — delivery zone polygons
- [ ] **Step 9: Create `supplier/` (~4 tools)** — supplier info
- [ ] **Step 10: Create `digital/` (~4 tools)** — digital product management
- [ ] **Step 11: Create `quants/` (~2 tools)** — economy segment products
- [ ] **Step 12: Create `rating/` (~2 tools)** — rating summary/history
- [ ] **Step 13: Create `brand/` (~1 tool)** — brand certificate
- [ ] **Step 14: Create `returns/` (~1 tool)** — return shipment lists

- [ ] **Step 15: Commit Wave 4**

```bash
git add src/tools/promos/ src/tools/chat/ src/tools/qa/ src/tools/review/ src/tools/category/ src/tools/beta/ src/tools/barcode/ src/tools/polygon/ src/tools/supplier/ src/tools/digital/ src/tools/quants/ src/tools/rating/ src/tools/brand/ src/tools/returns/
git commit -m "feat: add Wave 4 tool categories (promos, chat, qa, review, category, misc)"
```

---

## Task 12: Tool Registry

**Files:**
- Create: `src/tools/index.ts`

- [ ] **Step 1: Create src/tools/index.ts**

Aggregate all 33 categories:

```typescript
import { ToolDefinition, ToolHandler } from '../types/tools.js';

import { productTools, productHandlers } from './product/index.js';
import { fbsTools, fbsHandlers } from './fbs/index.js';
import { fboTools, fboHandlers } from './fbo/index.js';
import { fboSupplyTools, fboSupplyHandlers } from './fbo-supply/index.js';
import { deliveryFbsTools, deliveryFbsHandlers } from './delivery-fbs/index.js';
import { fbsMarksTools, fbsMarksHandlers } from './fbs-marks/index.js';
import { deliveryRfbsTools, deliveryRfbsHandlers } from './delivery-rfbs/index.js';
import { pricingStrategyTools, pricingStrategyHandlers } from './pricing-strategy/index.js';
import { certificationTools, certificationHandlers } from './certification/index.js';
import { financeTools, financeHandlers } from './finance/index.js';
import { pricesStocksTools, pricesStocksHandlers } from './prices-stocks/index.js';
import { betaTools, betaHandlers } from './beta/index.js';
import { returnFboTools, returnFboHandlers } from './return-fbo/index.js';
import { returnRfbsTools, returnRfbsHandlers } from './return-rfbs/index.js';
import { reportTools, reportHandlers } from './report/index.js';
import { premiumTools, premiumHandlers } from './premium/index.js';
import { promosTools, promosHandlers } from './promos/index.js';
import { chatTools, chatHandlers } from './chat/index.js';
import { qaTools, qaHandlers } from './qa/index.js';
import { reviewTools, reviewHandlers } from './review/index.js';
import { passTools, passHandlers } from './pass/index.js';
import { cancellationTools, cancellationHandlers } from './cancellation/index.js';
import { categoryTools, categoryHandlers } from './category/index.js';
import { barcodeTools, barcodeHandlers } from './barcode/index.js';
import { polygonTools, polygonHandlers } from './polygon/index.js';
import { supplierTools, supplierHandlers } from './supplier/index.js';
import { digitalTools, digitalHandlers } from './digital/index.js';
import { analyticsTools, analyticsHandlers } from './analytics/index.js';
import { warehouseTools, warehouseHandlers } from './warehouse/index.js';
import { quantsTools, quantsHandlers } from './quants/index.js';
import { ratingTools, ratingHandlers } from './rating/index.js';
import { brandTools, brandHandlers } from './brand/index.js';
import { returnsTools, returnsHandlers } from './returns/index.js';

export const allTools: ToolDefinition[] = [
  ...productTools, ...fbsTools, ...fboTools, ...fboSupplyTools,
  ...deliveryFbsTools, ...fbsMarksTools, ...deliveryRfbsTools,
  ...pricingStrategyTools, ...certificationTools, ...financeTools,
  ...pricesStocksTools, ...betaTools, ...returnFboTools, ...returnRfbsTools,
  ...reportTools, ...premiumTools, ...promosTools, ...chatTools,
  ...qaTools, ...reviewTools, ...passTools, ...cancellationTools,
  ...categoryTools, ...barcodeTools, ...polygonTools, ...supplierTools,
  ...digitalTools, ...analyticsTools, ...warehouseTools, ...quantsTools,
  ...ratingTools, ...brandTools, ...returnsTools,
];

export const allHandlers: Record<string, ToolHandler> = {
  ...productHandlers, ...fbsHandlers, ...fboHandlers, ...fboSupplyHandlers,
  ...deliveryFbsHandlers, ...fbsMarksHandlers, ...deliveryRfbsHandlers,
  ...pricingStrategyHandlers, ...certificationHandlers, ...financeHandlers,
  ...pricesStocksHandlers, ...betaHandlers, ...returnFboHandlers, ...returnRfbsHandlers,
  ...reportHandlers, ...premiumHandlers, ...promosHandlers, ...chatHandlers,
  ...qaHandlers, ...reviewHandlers, ...passHandlers, ...cancellationHandlers,
  ...categoryHandlers, ...barcodeHandlers, ...polygonHandlers, ...supplierHandlers,
  ...digitalHandlers, ...analyticsHandlers, ...warehouseHandlers, ...quantsHandlers,
  ...ratingHandlers, ...brandHandlers, ...returnsHandlers,
};

export function getHandler(name: string): ToolHandler | undefined {
  return allHandlers[name];
}
```

- [ ] **Step 2: Commit**

```bash
git add src/tools/index.ts
git commit -m "feat: add central tool registry aggregating all 33 categories"
```

---

## Task 13: Build & Smoke Test

**Agent:** Agent 3 (Tester)

- [ ] **Step 1: Build the project**

```bash
cd ~/Desktop/Документы/Cursor/ozon-mcp-server
npm run build
```

Expected: Clean compilation, `dist/` directory created with JS files.

- [ ] **Step 2: Fix any TypeScript errors**

If build fails, fix type errors in the reported files. Common issues:
- Missing imports
- Inconsistent types between tool definitions and handlers
- Missing category exports in index files

- [ ] **Step 3: Test stdio transport starts**

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | node dist/index.js 2>/dev/null | head -1
```

Expected: JSON response with server capabilities.

- [ ] **Step 4: Test tool listing**

```bash
echo -e '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}\n{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' | node dist/index.js 2>/dev/null
```

Expected: JSON with all registered tools (count should be ~278).

- [ ] **Step 5: Commit build fixes**

```bash
git add -A
git commit -m "fix: resolve build errors and verify server starts"
```

---

## Task 14: Integration Testing with Real API

**Agent:** Agent 3 (Tester)

Test key endpoints from each wave with real API keys (ИП account).

- [ ] **Step 1: Test product/list endpoint**

```bash
echo -e '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}\n{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"ozon_product_list","arguments":{"limit":5}}}' | node dist/index.js 2>/dev/null
```

Expected: JSON with product list data from Ozon API.

- [ ] **Step 2: Test finance/transaction/list**

```bash
echo -e '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}\n{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"ozon_finance_transaction_list","arguments":{"filter":{"date":{"from":"2026-04-01T00:00:00.000Z","to":"2026-04-06T23:59:59.999Z"}},"page":1,"page_size":10}}}' | node dist/index.js 2>/dev/null
```

Expected: Financial transaction data.

- [ ] **Step 3: Test warehouse/list**

```bash
echo -e '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}\n{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"ozon_warehouse_list","arguments":{}}}' | node dist/index.js 2>/dev/null
```

Expected: List of warehouses.

- [ ] **Step 4: Test analytics/data**

```bash
echo -e '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}\n{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"ozon_analytics_data","arguments":{"date_from":"2026-04-01","date_to":"2026-04-06","metrics":["revenue","ordered_units"],"dimension":["day"]}}}' | node dist/index.js 2>/dev/null
```

Expected: Analytics data.

- [ ] **Step 5: Test error handling (invalid endpoint)**

Test that a bad request returns a clean error, not a crash.

- [ ] **Step 6: Fix any issues found and commit**

```bash
git add -A
git commit -m "fix: address integration test findings"
```

---

## Task 15: README & Documentation

**Agent:** Agent 4 (Coordinator)

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Write comprehensive README.md**

Include:
- Project description
- Setup instructions (clone, npm install, .env)
- Available tool categories with counts
- Usage examples (stdio, http)
- Multi-account configuration
- Tool naming convention (`ozon_` prefix)
- Full tool list organized by category

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add comprehensive README with tool catalog"
```

---

## Task 16: Register in Wookiee

**Agent:** Agent 4 (Coordinator)

**Files:**
- Modify: `~/Desktop/Документы/Cursor/Wookiee/.mcp.json`

- [ ] **Step 1: Add ozon server to .mcp.json**

Add to the `mcpServers` object:

```json
"ozon": {
  "type": "stdio",
  "command": "node",
  "args": ["../ozon-mcp-server/dist/index.js"],
  "env": {
    "OZON_CLIENT_ID": "1410333",
    "OZON_API_KEY": "82ad849b-4cf6-4a15-9151-702787e80764"
  }
}
```

- [ ] **Step 2: Verify MCP server loads in Claude Code**

Test that the server appears in Claude Code's tool list.

- [ ] **Step 3: Commit in Wookiee repo**

```bash
cd ~/Desktop/Документы/Cursor/Wookiee
git add .mcp.json
git commit -m "feat: register ozon-mcp-server in MCP config"
```

---

## Task 17: Create GitHub Repository

- [ ] **Step 1: Create remote repo**

```bash
cd ~/Desktop/Документы/Cursor/ozon-mcp-server
gh repo create ozon-mcp-server --private --source=. --push
```

- [ ] **Step 2: Verify remote**

```bash
git remote -v
git log --oneline
```

Expected: All commits pushed to GitHub.

---

## Summary

| Wave | Categories | ~Tools | Tasks |
|------|-----------|--------|-------|
| Setup | Project init, types, config, client, index | 0 | 1-6 |
| Research | API catalog from docs | 0 | 7 |
| Wave 1 | product, fbs, fbo, finance, prices-stocks, analytics, warehouse | 81 | 8 |
| Wave 2 | fbo-supply, delivery-fbs, fbs-marks, delivery-rfbs, pass, cancellation | 72 | 9 |
| Wave 3 | pricing-strategy, certification, return-fbo, return-rfbs, report, premium | 56 | 10 |
| Wave 4 | promos, chat, qa, review, category, beta, barcode, polygon, supplier, digital, quants, rating, brand, returns | 69 | 11 |
| Registry | Tool index | 0 | 12 |
| Test | Build, smoke, integration | 0 | 13-14 |
| Finalize | README, Wookiee registration, GitHub | 0 | 15-17 |
| **Total** | **33 categories** | **~278** | **17 tasks** |
