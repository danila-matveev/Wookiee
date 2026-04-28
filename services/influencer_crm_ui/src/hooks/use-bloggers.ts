import { useInfiniteQuery } from '@tanstack/react-query';
import { listBloggers, type BloggerListParams } from '@/api/bloggers';

export function useBloggers(params: Omit<BloggerListParams, 'cursor'> = {}) {
  return useInfiniteQuery({
    queryKey: ['bloggers', params],
    queryFn: ({ pageParam }) => listBloggers({ ...params, cursor: pageParam }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  });
}
