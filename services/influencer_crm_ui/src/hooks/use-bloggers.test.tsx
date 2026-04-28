import { QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { createQueryClient } from '@/lib/query-client';
import { useBloggers } from './use-bloggers';

describe('useBloggers', () => {
  it('fetches first page', async () => {
    const client = createQueryClient();
    const { result } = renderHook(() => useBloggers(), {
      wrapper: ({ children }) => (
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
      ),
    });
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data?.pages[0]?.items[0]?.handle).toBe('_anna.blog');
  });
});
