import { useId, useMemo, useState } from 'react';
import { NavLink } from 'react-router-dom';
import type { ProductOut } from '@/api/products';
import { formatRub } from '@/lib/format';
import { useProducts } from '@/hooks/use-products';
import { PageHeader } from '@/layout/PageHeader';
import { Button } from '@/ui/Button';
import { FilterPill } from '@/ui/FilterPill';
import { Input } from '@/ui/Input';
import { QueryStatusBoundary } from '@/ui/QueryStatusBoundary';
import { ProductSliceCard } from './ProductSliceCard';

// Stable per-model placeholder color. Real thumbnails would be image URLs from
// modeli_osnova; the BFF doesn't ship those yet, so we hash the name into a hue
// to keep the UI from looking samey while we wait.
function placeholderHue(name: string): number {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) % 360;
  return h;
}

interface ProductCardProps {
  product: ProductOut;
  selected: boolean;
  onSelect: () => void;
}

function ProductCard({ product, selected, onSelect }: ProductCardProps) {
  const hue = placeholderHue(product.model_name || String(product.model_osnova_id));
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`text-left bg-card border rounded-lg shadow-warm p-4 transition-colors cursor-pointer ${
        selected
          ? 'border-primary ring-2 ring-primary/30'
          : 'border-border-strong hover:border-primary-muted'
      }`}
      aria-pressed={selected}
    >
      <div className="flex items-start gap-3">
        <div
          className="w-14 h-14 rounded-md shrink-0"
          style={{ background: `hsl(${hue} 70% 78%)` }}
          aria-hidden
        />
        <div className="min-w-0 flex-1">
          <div className="font-display text-base font-semibold text-fg truncate">
            {product.model_name || `Модель #${product.model_osnova_id}`}
          </div>
          <div className="text-xs text-muted-fg mt-0.5">ID {product.model_osnova_id}</div>
        </div>
      </div>
      <dl className="mt-4 grid grid-cols-3 gap-2 text-xs">
        <div>
          <dt className="text-muted-fg uppercase tracking-wider text-[10px]">Интеграций</dt>
          <dd className="font-mono text-sm text-fg">
            {product.integrations_count}
            <span className="text-muted-fg"> / {product.integrations_done}</span>
          </dd>
        </div>
        <div>
          <dt className="text-muted-fg uppercase tracking-wider text-[10px]">Расход</dt>
          <dd className="font-mono text-sm text-fg">{formatRub(product.total_spent)}</dd>
        </div>
        <div>
          <dt className="text-muted-fg uppercase tracking-wider text-[10px]">Выручка</dt>
          <dd className="font-mono text-sm text-fg">{formatRub(product.total_revenue_fact)}</dd>
        </div>
      </dl>
    </button>
  );
}

export function ProductsPage() {
  const [search, setSearch] = useState('');
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const searchId = useId();

  const { data, isLoading, error, fetchNextPage, hasNextPage, isFetchingNextPage } = useProducts();
  const allItems = useMemo(() => data?.pages.flatMap((p) => p.items) ?? [], [data?.pages]);

  // Client-side filter only — the BFF /products endpoint doesn't currently
  // support a search query param. When it does, lift this into useProducts({q}).
  const items = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return allItems;
    return allItems.filter((p) => p.model_name.toLowerCase().includes(q));
  }, [allItems, search]);

  return (
    <>
      <PageHeader
        title="Продукты"
        sub="Каталог моделей Wookiee — связь с интеграциями и аналитикой."
      />

      <div className="flex items-center gap-2 mb-5">
        <FilterPill active solid>
          Каталог
        </FilterPill>
        <NavLink to="/slices">
          {({ isActive }) => (
            <FilterPill active={isActive} type="button" tabIndex={-1}>
              Срезы
            </FilterPill>
          )}
        </NavLink>
      </div>

      <div className="bg-card border border-border rounded-lg shadow-warm px-3.5 py-3 mb-5 flex items-center gap-2.5 flex-wrap">
        <label
          htmlFor={searchId}
          className="text-[11px] uppercase tracking-wider text-muted-fg font-semibold"
        >
          Поиск
        </label>
        <Input
          id={searchId}
          className="ml-auto max-w-xs"
          placeholder="Поиск по названию модели"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <QueryStatusBoundary
        isLoading={isLoading}
        error={error}
        isEmpty={items.length === 0}
        emptyTitle="Моделей не нашлось"
        emptyDescription={
          search
            ? 'Уберите часть поискового запроса.'
            : 'У моделей пока нет интеграций — каталог пуст.'
        }
      >
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {items.map((p) => (
            <ProductCard
              key={p.model_osnova_id}
              product={p}
              selected={selectedId === p.model_osnova_id}
              onSelect={() =>
                setSelectedId((prev) => (prev === p.model_osnova_id ? null : p.model_osnova_id))
              }
            />
          ))}
        </div>
      </QueryStatusBoundary>

      {hasNextPage && (
        <div className="flex justify-center mt-4">
          <Button onClick={() => fetchNextPage()} loading={isFetchingNextPage}>
            Показать ещё
          </Button>
        </div>
      )}

      {selectedId !== null && (
        <ProductSliceCard modelOsnovaId={selectedId} onClose={() => setSelectedId(null)} />
      )}
    </>
  );
}

export default ProductsPage;
