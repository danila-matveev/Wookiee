import { useInfiniteQuery, useQuery } from '@tanstack/react-query';
import { getProduct, listProducts, type ProductListParams } from '@/api/products';

export function useProducts(params: Omit<ProductListParams, 'cursor'> = {}) {
  return useInfiniteQuery({
    queryKey: ['products', params],
    queryFn: ({ pageParam }) => listProducts({ ...params, cursor: pageParam }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  });
}

export function useProduct(modelOsnovaId: number | undefined) {
  return useQuery({
    queryKey: ['product', modelOsnovaId],
    queryFn: () => getProduct(modelOsnovaId as number),
    enabled: typeof modelOsnovaId === 'number' && modelOsnovaId > 0,
  });
}
