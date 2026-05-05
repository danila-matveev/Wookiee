import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  type BloggerInput,
  type BloggerListParams,
  type BloggerOut,
  createBlogger,
  getBlogger,
  listBloggers,
  updateBlogger,
} from '@/api/bloggers';

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

export interface UpsertBloggerArgs {
  id?: number;
  body: BloggerInput | Partial<BloggerInput>;
}

export function useUpsertBlogger() {
  const qc = useQueryClient();
  return useMutation<BloggerOut, Error, UpsertBloggerArgs>({
    mutationFn: ({ id, body }) =>
      id ? updateBlogger(id, body) : createBlogger(body as BloggerInput),
    onSuccess: (saved) => {
      qc.invalidateQueries({ queryKey: ['bloggers'] });
      qc.invalidateQueries({ queryKey: ['blogger', saved.id] });
    },
  });
}
