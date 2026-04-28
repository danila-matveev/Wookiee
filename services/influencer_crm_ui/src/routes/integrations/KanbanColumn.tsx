import { useDroppable } from '@dnd-kit/core';
import type { IntegrationOut, Stage } from '@/api/integrations';
import { STAGE_LABELS } from '@/api/integrations';
import { cn } from '@/lib/cn';
import { Badge } from '@/ui/Badge';
import { KanbanCard } from './KanbanCard';

interface KanbanColumnProps {
  stage: Stage;
  items: IntegrationOut[];
}

export function KanbanColumn({ stage, items }: KanbanColumnProps) {
  const { setNodeRef, isOver } = useDroppable({ id: stage });

  return (
    <div
      ref={setNodeRef}
      data-testid={`kanban-column-${stage}`}
      className={cn(
        'flex h-full w-[280px] flex-shrink-0 flex-col rounded-xl border border-border bg-muted/30 p-3 transition-colors',
        isOver && 'border-primary bg-primary-light/40',
      )}
    >
      <header className="mb-3 flex items-center justify-between">
        <h3 className="font-display text-sm font-semibold text-fg">{STAGE_LABELS[stage]}</h3>
        <Badge tone="secondary">{items.length}</Badge>
      </header>
      <div className="flex flex-1 flex-col gap-2 overflow-y-auto">
        {items.length === 0 ? (
          <p className="rounded-md border border-dashed border-border px-2 py-6 text-center text-xs text-muted-fg">
            Пусто
          </p>
        ) : (
          items.map((it) => <KanbanCard key={it.id} integration={it} />)
        )}
      </div>
    </div>
  );
}

export default KanbanColumn;
