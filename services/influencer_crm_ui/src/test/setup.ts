import '@testing-library/jest-dom/vitest';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, vi } from 'vitest';
import { handlers } from './msw-handlers';

// Default test env. Individual tests may still override via direct mutation
// or vi.stubEnv. With VITE_API_BASE_URL='/api', listBloggers() → '/api/bloggers',
// which matches the MSW handler URL pattern.
vi.stubEnv('VITE_API_BASE_URL', '/api');
vi.stubEnv('VITE_API_KEY', 'test-key');

const server = setupServer(...handlers);
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
