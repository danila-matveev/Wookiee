import { DndContext, type DragEndEvent, PointerSensor, useSensor, useSensors } from '@dnd-kit/core';
import { useMemo } from 'react';
import type { IntegrationOut, Stage } from '@/api/integrations';
import { STAGES } from '@/api/integrations';
import { useIntegrations, useUpdateIntegrationStage } from '@/hooks/use-integrations';
import { PageHeader } from '@/layout/PageHeader';
import { EmptyState } from '@/ui/EmptyState';
import { Skeleton } from '@/ui/Skeleton';
import { KanbanColumn } from './KanbanColumn';

type StageGroups = Record<Stage, IntegrationOut[]>;

function emptyGroups(): StageGroups {
  return STAGES.reduce<StageGroups>((acc, stage) => {
    acc[stage] = [];
    return acc;
  }, {} as StageGroups);
}

export function IntegrationsKanbanPage() {
  const { data, isLoading, isError } = useIntegrations({ limit: 200 });
  const updateStage = useUpdateIntegrationStage();

  // 5px activation distance: lets click-to-open (T13) coexist with drag.
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
        sub="10 стадий — перетащи карточку для смены стадии. Клик откроет детали (в разработке)."
      />
      {isLoading ? (
        <Skeleton className="h-96" />
      ) : isError ? (
        <EmptyState
          title="Не удалось загрузить интеграции"
          description="Попробуйте обновить страницу."
        />
      ) : items.length === 0 ? (
        <EmptyState
          title="Интеграций пока нет"
          description="Создайте первую интеграцию из карточки блогера."
        />
      ) : (
        <DndContext sensors={sensors} onDragEnd={onDragEnd}>
          <div className="-mx-2 flex gap-4 overflow-x-auto px-2 pb-4">
            {STAGES.map((stage) => (
              <KanbanColumn key={stage} stage={stage} items={groups[stage]} />
            ))}
          </div>
        </DndContext>
      )}
    </>
  );
}

export default IntegrationsKanbanPage;
