import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useBloggers } from '@/hooks/crm/use-bloggers';
import { PageHeader } from '@/components/crm/layout/PageHeader';
import { Button } from '@/components/crm/ui/Button';
import { QueryStatusBoundary } from '@/components/crm/ui/QueryStatusBoundary';
import { BloggerEditDrawer } from './BloggerEditDrawer';
import { BloggersFilters, type BloggersFilterValue } from './BloggersFilters';
import { BloggersTable } from './BloggersTable';
import { BloggersTableView } from './BloggersTableView';

export function BloggersPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const view = (searchParams.get('view') as 'cards' | 'table') ?? 'cards';
  const [filters, setFilters] = useState<BloggersFilterValue>({ status: 'active' });
  const [platformFilter, setPlatformFilter] = useState<string | undefined>();
  const { data, isLoading, error, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useBloggers({ ...filters, channel: platformFilter });
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

  const openDrawer = (id: number) => {
    setSearchParams((prev) => {
      prev.set('open', String(id));
      return prev;
    });
  };

  const summaryParams = {
    q: filters.q,
    channel: platformFilter,
    limit: 300,
  };

  return (
    <>
      <PageHeader
        title="Блогеры"
        sub="Все блогеры в работе. Клик по строке — детали и история интеграций."
        actions={
          <div className="flex items-center gap-2">
            <div className="flex gap-1">
              <button
                className={`px-3 py-1.5 text-sm rounded transition-colors ${view === 'cards' ? 'bg-primary text-primary-fg' : 'bg-muted text-muted-fg hover:bg-muted/80'}`}
                onClick={() =>
                  setSearchParams((prev) => {
                    prev.set('view', 'cards');
                    return prev;
                  })
                }
              >
                Карточки
              </button>
              <button
                className={`px-3 py-1.5 text-sm rounded transition-colors ${view === 'table' ? 'bg-primary text-primary-fg' : 'bg-muted text-muted-fg hover:bg-muted/80'}`}
                onClick={() =>
                  setSearchParams((prev) => {
                    prev.set('view', 'table');
                    return prev;
                  })
                }
              >
                Таблица
              </button>
            </div>
            <Button variant="primary" onClick={openCreate}>
              + Новый блогер
            </Button>
          </div>
        }
      />
      <div className="flex flex-wrap gap-1.5 mb-4">
        {(
          [
            { ch: 'instagram', label: 'IG' },
            { ch: 'telegram', label: 'TG' },
            { ch: 'tiktok', label: 'TikTok' },
            { ch: 'youtube', label: 'YT' },
            { ch: 'vk', label: 'VK' },
          ] as const
        ).map(({ ch, label }) => (
          <button
            key={ch}
            onClick={() => setPlatformFilter(platformFilter === ch ? undefined : ch)}
            className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${
              platformFilter === ch
                ? 'bg-primary text-primary-fg border-primary'
                : 'border-border text-muted-fg hover:border-primary/50'
            }`}
          >
            {label}
          </button>
        ))}
        {platformFilter && (
          <button
            onClick={() => setPlatformFilter(undefined)}
            className="text-xs px-2.5 py-1 rounded-full text-muted-fg hover:text-fg"
          >
            × Сбросить
          </button>
        )}
      </div>
      <BloggersFilters value={filters} onChange={setFilters} />
      {view === 'table' ? (
        <BloggersTableView params={summaryParams} onRowClick={openDrawer} />
      ) : (
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
      )}
      {view === 'cards' && hasNextPage && (
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
