import { useDraggable } from '@dnd-kit/core';
import type { CSSProperties } from 'react';
import type { IntegrationOut, Marketplace } from '@/api/integrations';
import { cn } from '@/lib/cn';
import { Avatar } from '@/ui/Avatar';
import { Badge } from '@/ui/Badge';
import { type PlatformChannel, PlatformPill } from '@/ui/PlatformPill';

const MARKETPLACE_LABEL: Record<Marketplace, string> = {
  wb: 'WB',
  ozon: 'OZON',
  both: 'WB+OZON',
};

const SUPPORTED_PILL_CHANNELS: ReadonlySet<string> = new Set([
  'instagram',
  'telegram',
  'tiktok',
  'youtube',
  'vk',
]);

function formatDate(iso: string): string {
  // Compact ru-RU date — '12.05'
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    const dd = String(d.getDate()).padStart(2, '0');
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    return `${dd}.${mm}`;
  } catch {
    return iso;
  }
}

function formatCost(value: string): string {
  const num = Number(value);
  if (!Number.isFinite(num) || num === 0) return '—';
  return new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(num);
}

interface KanbanCardProps {
  integration: IntegrationOut;
  onOpen?: (id: number) => void;
}

export function KanbanCard({ integration, onOpen }: KanbanCardProps) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: String(integration.id),
  });

  const style: CSSProperties | undefined = transform
    ? {
        transform: `translate3d(${transform.x}px, ${transform.y}px, 0)`,
        zIndex: isDragging ? 50 : undefined,
      }
    : undefined;

  const handleLabel = `Блогер #${integration.blogger_id}`;
  const channel = integration.channel;
  const showPill = SUPPORTED_PILL_CHANNELS.has(channel);

  // Click vs drag coexistence: dnd-kit's PointerSensor with activationConstraint.distance=5
  // only consumes pointer events as a drag once the pointer has moved >= 5px. Below that
  // threshold the synthetic click fires normally — so we can attach onClick directly. The
  // explicit isDragging guard is cheap insurance in case dnd-kit ever lets a stray click slip.
  function handleClick() {
    if (isDragging) return;
    onOpen?.(integration.id);
  }

  return (
    <button
      ref={setNodeRef}
      type="button"
      style={style}
      {...attributes}
      {...listeners}
      onClick={handleClick}
      data-testid={`kanban-card-${integration.id}`}
      className={cn(
        'block w-full text-left',
        'cursor-grab touch-none select-none rounded-lg border border-border bg-surface p-3 shadow-sm',
        'hover:border-primary-light hover:shadow',
        'focus:outline-none focus:ring-2 focus:ring-primary/30',
        isDragging && 'border-primary outline outline-2 outline-primary-light/60 opacity-90',
      )}
    >
      <div className="flex items-center gap-2">
        <Avatar size="xs" name={handleLabel} />
        <span className="font-display text-sm font-semibold text-fg truncate">{handleLabel}</span>
        {showPill && <PlatformPill channel={channel as PlatformChannel} className="ml-auto" />}
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        <Badge tone="secondary">{formatDate(integration.publish_date)}</Badge>
        {integration.brief_id != null && <Badge tone="info">ТЗ #{integration.brief_id}</Badge>}
        {integration.is_barter && <Badge tone="pink">Бартер</Badge>}
      </div>

      <div className="mt-2 flex items-center justify-between">
        <span className="font-mono text-xs text-muted-fg">
          {formatCost(integration.total_cost)} ₽
        </span>
        <Badge tone="orange">{MARKETPLACE_LABEL[integration.marketplace]}</Badge>
      </div>
    </button>
  );
}

export default KanbanCard;
