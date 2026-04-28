import { QueryClient } from '@tanstack/react-query';

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        gcTime: 5 * 60_000,
        retry: (count, err: unknown) => {
          const status = (err as { status?: number } | null)?.status;
          return count < 2 && status !== 404 && status !== 403;
        },
        refetchOnWindowFocus: false,
      },
    },
  });
}
