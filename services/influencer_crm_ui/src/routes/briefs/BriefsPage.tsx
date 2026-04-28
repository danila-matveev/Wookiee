import { Plus } from 'lucide-react';
import { useMemo, useState } from 'react';
import { BRIEF_STATUS_LABELS, BRIEF_STATUSES, type BriefOut, type BriefStatus } from '@/api/briefs';
import { useBriefs } from '@/hooks/use-briefs';
import { PageHeader } from '@/layout/PageHeader';
import { Badge } from '@/ui/Badge';
import { Button } from '@/ui/Button';
import { EmptyState } from '@/ui/EmptyState';
import { FilterPill } from '@/ui/FilterPill';
import { Skeleton } from '@/ui/Skeleton';
import { BriefCard } from './BriefCard';
import { BriefEditorDrawer } from './BriefEditorDrawer';

type BriefGroups = Record<BriefStatus, BriefOut[]>;

function emptyGroups(): BriefGroups {
  return BRIEF_STATUSES.reduce<BriefGroups>((acc, s) => {
    acc[s] = [];
    return acc;
  }, {} as BriefGroups);
}

export function BriefsPage() {
  const { data, isLoading, isError } = useBriefs({ limit: 200 });
  // undefined = drawer closed; 0 = create mode; >0 = edit mode for that id.
  const [activeId, setActiveId] = useState<number | undefined>(undefined);
  const [statusFilter, setStatusFilter] = useState<BriefStatus | 'all'>('all');

  const items = data?.items ?? [];

  const groups = useMemo(() => {
    const acc = emptyGroups();
    for (const b of items) {
      if (acc[b.status]) acc[b.status].push(b);
    }
    return acc;
  }, [items]);

  const visibleStatuses: BriefStatus[] =
    statusFilter === 'all' ? [...BRIEF_STATUSES] : [statusFilter];

  return (
    <>
      <PageHeader
        title="Брифы"
        sub="ТЗ для блогеров — Kanban по статусам, создание новых версий, история изменений."
        actions={
          <Button variant="primary" onClick={() => setActiveId(0)}>
            <Plus size={16} /> Новый бриф
          </Button>
        }
      />

      <div className="mb-4 flex flex-wrap gap-2">
        <FilterPill active={statusFilter === 'all'} onClick={() => setStatusFilter('all')}>
          Все
          <span className="ml-1 font-mono text-[11px]">{items.length}</span>
        </FilterPill>
        {BRIEF_STATUSES.map((s) => (
          <FilterPill key={s} active={statusFilter === s} onClick={() => setStatusFilter(s)}>
            {BRIEF_STATUS_LABELS[s]}
            <span className="ml-1 font-mono text-[11px]">{groups[s].length}</span>
          </FilterPill>
        ))}
      </div>

      {isLoading ? (
        <Skeleton className="h-96" />
      ) : isError ? (
        <EmptyState
          title="Не удалось загрузить брифы"
          description="Попробуйте обновить страницу."
        />
      ) : (
        <div
          className={
            statusFilter === 'all'
              ? 'grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4'
              : 'flex flex-col gap-3'
          }
        >
          {visibleStatuses.map((s) => (
            <section
              key={s}
              data-testid={`brief-column-${s}`}
              className="flex flex-col rounded-xl border border-border bg-muted/30 p-3"
            >
              <header className="mb-3 flex items-center justify-between">
                <h3 className="font-display text-sm font-semibold text-fg">
                  {BRIEF_STATUS_LABELS[s]}
                </h3>
                <Badge tone="secondary">{groups[s].length}</Badge>
              </header>
              <div className="flex flex-1 flex-col gap-2">
                {groups[s].length === 0 ? (
                  <p className="rounded-md border border-dashed border-border px-2 py-6 text-center text-xs text-muted-fg">
                    Пусто
                  </p>
                ) : (
                  groups[s].map((b) => (
                    <BriefCard key={b.id} brief={b} onOpen={(id) => setActiveId(id)} />
                  ))
                )}
              </div>
            </section>
          ))}
        </div>
      )}

      <BriefEditorDrawer
        open={activeId !== undefined}
        id={activeId !== undefined && activeId > 0 ? activeId : undefined}
        onClose={() => setActiveId(undefined)}
      />
    </>
  );
}

export default BriefsPage;
