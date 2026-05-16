import { DndContext, type DragEndEvent, PointerSensor, useSensor, useSensors } from '@dnd-kit/core';
import { Plus } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import type { Channel, IntegrationOut, Marketplace, Stage } from '@/api/crm/integrations';
import { STAGES } from '@/api/crm/integrations';
import { useIntegrations, useUpdateIntegrationStage } from '@/hooks/crm/use-integrations';
import { PageHeader } from '@/components/layout/page-header';
import { Button } from '@/components/crm/ui/Button';
import { QueryStatusBoundary } from '@/components/crm/ui/QueryStatusBoundary';
import { IntegrationEditDrawer } from './IntegrationEditDrawer';
import { IntegrationFilters, type IntegrationFilterValue } from './IntegrationFilters';
import { IntegrationsTableView } from './IntegrationsTableView';
import { KanbanColumn } from './KanbanColumn';

type StageGroups = Record<Stage, IntegrationOut[]>;

function emptyGroups(): StageGroups {
  return STAGES.reduce<StageGroups>((acc, stage) => {
    acc[stage] = [];
    return acc;
  }, {} as StageGroups);
}

function getDefaultDates(): { date_from: string; date_to: string } {
  const now = new Date();
  const firstLastMonth = new Date(now.getFullYear(), now.getMonth() - 1, 1);
  const lastCurrentMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0);
  const fmt = (d: Date) => d.toISOString().slice(0, 10);
  return { date_from: fmt(firstLastMonth), date_to: fmt(lastCurrentMonth) };
}

export function IntegrationsKanbanPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const view = (searchParams.get('view') as 'kanban' | 'table') ?? 'kanban';
  const [filters, setFilters] = useState<IntegrationFilterValue>(getDefaultDates);
  const [activeId, setActiveId] = useState<number | undefined>(undefined);

  const queryParams = {
    q: filters.q,
    channel: filters.channel as Channel | undefined,
    stage_in: filters.stage_in as Stage[] | undefined,
    date_from: filters.date_from,
    date_to: filters.date_to,
    marketplace: filters.marketplace as Marketplace | undefined,
    limit: 500,
  };

  const { data, isLoading, error } = useIntegrations(queryParams);
  const updateStage = useUpdateIntegrationStage();

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));

  const integrations = data?.items ?? [];

  const groups = useMemo(() => {
    const acc = emptyGroups();
    for (const it of integrations) {
      if (acc[it.stage]) acc[it.stage].push(it);
    }
    return acc;
  }, [integrations]);

  function onDragEnd(e: DragEndEvent) {
    const id = Number(e.active.id);
    const target = e.over?.id;
    if (!Number.isFinite(id) || target == null) return;
    const stage = target as Stage;
    if (!STAGES.includes(stage)) return;
    const current = integrations.find((i) => i.id === id);
    if (!current || current.stage === stage) return;
    updateStage.mutate({ id, stage });
  }

  return (
    <>
      <PageHeader
        kicker="ИНФЛЮЕНС"
        title="Интеграции"
        breadcrumbs={[
          { label: 'Инфлюенс', to: '/influence/bloggers' },
          { label: 'Интеграции', to: '/influence/integrations' },
        ]}
        description="8 стадий — перетащи карточку для смены стадии. Клик откроет детали."
        actions={
          <div className="flex items-center gap-2">
            {/* View toggle */}
            <div className="flex gap-1">
              <button
                type="button"
                className={`px-3 py-1.5 text-sm rounded ${view === 'kanban' ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-fg hover:bg-muted/80'}`}
                onClick={() => setSearchParams({ view: 'kanban' })}
              >
                Канбан
              </button>
              <button
                type="button"
                className={`px-3 py-1.5 text-sm rounded ${view === 'table' ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-fg hover:bg-muted/80'}`}
                onClick={() => setSearchParams({ view: 'table' })}
              >
                Таблица
              </button>
            </div>

            <Button variant="primary" onClick={() => setActiveId(0)}>
              <Plus size={16} /> Новая интеграция
            </Button>
          </div>
        }
      />

      {/* Filters bar */}
      <IntegrationFilters value={filters} onChange={setFilters} />

      <QueryStatusBoundary
        isLoading={isLoading}
        error={error}
        isEmpty={integrations.length === 0}
        emptyTitle="Интеграций пока нет"
        emptyDescription="Создайте первую интеграцию из карточки блогера."
      >
        {view === 'table' ? (
          <IntegrationsTableView
            items={integrations}
            onRowClick={(id) => setActiveId(id)}
          />
        ) : (
          <DndContext sensors={sensors} onDragEnd={onDragEnd}>
            <div className="-mx-2 flex gap-4 overflow-x-auto px-2 pb-4">
              {STAGES.map((stage) => (
                <KanbanColumn
                  key={stage}
                  stage={stage}
                  items={groups[stage]}
                  onOpenCard={(id) => setActiveId(id)}
                />
              ))}
            </div>
          </DndContext>
        )}
      </QueryStatusBoundary>

      <IntegrationEditDrawer
        open={activeId !== undefined}
        id={activeId !== undefined && activeId > 0 ? activeId : undefined}
        onClose={() => setActiveId(undefined)}
      />
    </>
  );
}

export default IntegrationsKanbanPage;
