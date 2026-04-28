import { useState } from 'react';
import { useBloggers } from '@/hooks/use-bloggers';
import { PageHeader } from '@/layout/PageHeader';
import { Button } from '@/ui/Button';
import { EmptyState } from '@/ui/EmptyState';
import { Skeleton } from '@/ui/Skeleton';
import { BloggersFilters, type BloggersFilterValue } from './BloggersFilters';
import { BloggersTable } from './BloggersTable';

export function BloggersPage() {
  const [filters, setFilters] = useState<BloggersFilterValue>({ status: 'active' });
  const { data, isLoading, fetchNextPage, hasNextPage, isFetchingNextPage } = useBloggers(filters);
  const items = data?.pages.flatMap((p) => p.items) ?? [];

  return (
    <>
      <PageHeader
        title="Блогеры"
        sub="Все блогеры в работе. Клик по строке — детали и история интеграций."
        actions={<Button variant="primary">+ Новый блогер</Button>}
      />
      <BloggersFilters value={filters} onChange={setFilters} />
      {isLoading ? (
        <Skeleton className="h-96" />
      ) : items.length === 0 ? (
        <EmptyState title="Никого не нашлось" description="Снимите фильтр или создайте нового." />
      ) : (
        <BloggersTable bloggers={items} />
      )}
      {hasNextPage && (
        <div className="flex justify-center mt-4">
          <Button onClick={() => fetchNextPage()} loading={isFetchingNextPage}>
            Показать ещё
          </Button>
        </div>
      )}
    </>
  );
}

export default BloggersPage;
