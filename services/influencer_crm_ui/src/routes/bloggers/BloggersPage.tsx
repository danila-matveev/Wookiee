import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useBloggers } from '@/hooks/use-bloggers';
import { PageHeader } from '@/layout/PageHeader';
import { Button } from '@/ui/Button';
import { QueryStatusBoundary } from '@/ui/QueryStatusBoundary';
import { BloggerEditDrawer } from './BloggerEditDrawer';
import { BloggersFilters, type BloggersFilterValue } from './BloggersFilters';
import { BloggersTable } from './BloggersTable';

export function BloggersPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [filters, setFilters] = useState<BloggersFilterValue>({ status: 'active' });
  const { data, isLoading, error, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useBloggers(filters);
  const items = data?.pages.flatMap((p) => p.items) ?? [];

  const openParam = searchParams.get('open');
  const [drawerOpen, setDrawerOpen] = useState(() => openParam !== null);
  const [drawerBloggerId, setDrawerBloggerId] = useState<number | undefined>(
    () => (openParam ? Number(openParam) : undefined),
  );

  useEffect(() => {
    if (openParam !== null) {
      setDrawerBloggerId(Number(openParam));
      setDrawerOpen(true);
    }
  }, [openParam]);

  const openCreate = () => {
    setDrawerBloggerId(undefined);
    setDrawerOpen(true);
  };

  return (
    <>
      <PageHeader
        title="Блогеры"
        sub="Все блогеры в работе. Клик по строке — детали и история интеграций."
        actions={
          <Button variant="primary" onClick={openCreate}>
            + Новый блогер
          </Button>
        }
      />
      <BloggersFilters value={filters} onChange={setFilters} />
      <QueryStatusBoundary
        isLoading={isLoading}
        error={error}
        isEmpty={items.length === 0}
        emptyTitle="Никого не нашлось"
        emptyDescription="Снимите фильтр или создайте нового."
      >
        <BloggersTable
          bloggers={items}
          onEdit={(id) => {
            setDrawerBloggerId(id);
            setDrawerOpen(true);
          }}
        />
      </QueryStatusBoundary>
      {hasNextPage && (
        <div className="flex justify-center mt-4">
          <Button onClick={() => fetchNextPage()} loading={isFetchingNextPage}>
            Показать ещё
          </Button>
        </div>
      )}
      <BloggerEditDrawer
        open={drawerOpen}
        onClose={() => {
          setDrawerOpen(false);
          if (searchParams.has('open')) {
            setSearchParams((prev) => {
              prev.delete('open');
              return prev;
            });
          }
        }}
        bloggerId={drawerBloggerId}
      />
    </>
  );
}

export default BloggersPage;
