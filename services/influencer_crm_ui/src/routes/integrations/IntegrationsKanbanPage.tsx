import { DndContext, type DragEndEvent, PointerSensor, useSensor, useSensors } from '@dnd-kit/core';
import { Plus } from 'lucide-react';
import { useMemo, useState } from 'react';
import type { IntegrationOut, Stage } from '@/api/integrations';
import { STAGES } from '@/api/integrations';
import { useIntegrations, useUpdateIntegrationStage } from '@/hooks/use-integrations';
import { PageHeader } from '@/layout/PageHeader';
import { Button } from '@/ui/Button';
import { QueryStatusBoundary } from '@/ui/QueryStatusBoundary';
import { IntegrationEditDrawer } from './IntegrationEditDrawer';
import { KanbanColumn } from './KanbanColumn';

type StageGroups = Record<Stage, IntegrationOut[]>;

function emptyGroups(): StageGroups {
  return STAGES.reduce<StageGroups>((acc, stage) => {
    acc[stage] = [];
    return acc;
  }, {} as StageGroups);
}

export function IntegrationsKanbanPage() {
  const { data, isLoading, error } = useIntegrations({ limit: 200 });
  const updateStage = useUpdateIntegrationStage();
  // Drawer state: undefined = closed, 0 = open in create mode, >0 = open in edit mode for that id.
  const [activeId, setActiveId] = useState<number | undefined>(undefined);

  // 5px activation distance: lets click-to-open coexist with drag.
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));

  const items = data?.items ?? [];

  const groups = useMemo(() => {
    const acc = emptyGroups();
    for (const it of items) {
      // Defensive: ignore unknown stages from BFF (shouldn't happen).
      if (acc[it.stage]) acc[it.stage].push(it);
    }
    return acc;
  }, [items]);

  function onDragEnd(e: DragEndEvent) {
    const id = Number(e.active.id);
    const target = e.over?.id;
    if (!Number.isFinite(id) || target == null) return;
    const stage = target as Stage;
    if (!STAGES.includes(stage)) return;
    const current = items.find((i) => i.id === id);
    if (!current || current.stage === stage) return;
    updateStage.mutate({ id, stage });
  }

  return (
    <>
      <PageHeader
        title="Интеграции"
        sub="10 стадий — перетащи карточку для смены стадии. Клик откроет детали."
        actions={
          <Button variant="primary" onClick={() => setActiveId(0)}>
            <Plus size={16} /> Новая интеграция
          </Button>
        }
      />
      <QueryStatusBoundary
        isLoading={isLoading}
        error={error}
        isEmpty={items.length === 0}
        emptyTitle="Интеграций пока нет"
        emptyDescription="Создайте первую интеграцию из карточки блогера."
      >
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
