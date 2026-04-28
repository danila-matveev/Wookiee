import { useInfiniteQuery, useQuery } from '@tanstack/react-query';
import { type BloggerListParams, getBlogger, listBloggers } from '@/api/bloggers';

export function useBloggers(params: Omit<BloggerListParams, 'cursor'> = {}) {
  return useInfiniteQuery({
    queryKey: ['bloggers', params],
    queryFn: ({ pageParam }) => listBloggers({ ...params, cursor: pageParam }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  });
}

export function useBlogger(id: number) {
  return useQuery({
    queryKey: ['blogger', id],
    queryFn: () => getBlogger(id),
    enabled: id > 0,
  });
}
