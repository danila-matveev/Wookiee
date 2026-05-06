import { useDraggable } from '@dnd-kit/core';
import type { CSSProperties } from 'react';
import type { IntegrationOut, Marketplace } from '@/api/crm/integrations';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/crm/ui/Badge';
import { type PlatformChannel, PlatformPill } from '@/components/crm/ui/PlatformPill';

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

const AD_FORMAT_LABELS: Record<string, string> = {
  story: 'Story',
  short_video: 'Reels/Short',
  long_video: 'Long Video',
  long_post: 'Long Post',
  image_post: 'Image Post',
  integration: 'Integration',
  live_stream: 'Live',
};

const CHANNEL_LABELS: Record<string, string> = {
  instagram: 'Instagram',
  telegram: 'Telegram',
  tiktok: 'TikTok',
  youtube: 'YouTube',
  vk: 'VK',
  rutube: 'Rutube',
};

function handleToColor(handle: string): string {
  let hash = 0;
  for (let i = 0; i < handle.length; i++) {
    hash = handle.charCodeAt(i) + ((hash << 5) - hash);
  }
  const colors = ['#6366f1', '#8b5cf6', '#ec4899', '#f97316', '#14b8a6', '#3b82f6', '#84cc16'];
  return colors[Math.abs(hash) % colors.length];
}

function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    const dd = String(d.getDate()).padStart(2, '0');
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const yy = String(d.getFullYear()).slice(2);
    return `${dd}.${mm}.${yy}`;
  } catch {
    return iso;
  }
}

function formatCost(value: string): string {
  const num = Number(value);
  if (!Number.isFinite(num) || num === 0) return '—';
  return new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(num);
}

function formatViews(value: number): string {
  return new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(value);
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

  const handleLabel = integration.blogger_handle ?? `Блогер #${integration.blogger_id}`;
  const channel = integration.channel;
  const showPill = SUPPORTED_PILL_CHANNELS.has(channel);
  const avatarColor = handleToColor(handleLabel);
  const avatarLetter = handleLabel.charAt(0).toUpperCase();
  const cost = formatCost(integration.total_cost);
  const hasCost = cost !== '—';

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
      {/* Row 1: avatar + blogger handle + platform pill */}
      <div className="flex items-center gap-2">
        <span
          className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-bold text-white"
          style={{ backgroundColor: avatarColor }}
        >
          {avatarLetter}
        </span>
        <span className="font-display text-sm font-semibold text-fg truncate">{handleLabel}</span>
        {showPill && <PlatformPill channel={channel as PlatformChannel} className="ml-auto" />}
      </div>

      {/* Row 2: channel + ad_format */}
      <div className="mt-1.5 flex items-center gap-1.5">
        <span className="text-xs text-muted-fg">
          {CHANNEL_LABELS[channel] ?? channel}
        </span>
        <span className="text-xs text-muted-fg/60">·</span>
        <span className="text-xs text-muted-fg/80">
          {AD_FORMAT_LABELS[integration.ad_format] ?? integration.ad_format}
        </span>
        {integration.is_barter && (
          <>
            <span className="text-xs text-muted-fg/60">·</span>
            <Badge tone="pink">Бартер</Badge>
          </>
        )}
      </div>

      {/* Row 3: date (left) + cost (right) */}
      <div className="mt-2 flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <Badge tone="secondary">{formatDate(integration.publish_date)}</Badge>
          {integration.brief_id != null && <Badge tone="info">ТЗ #{integration.brief_id}</Badge>}
        </div>
        <div className="flex items-center gap-1.5">
          {hasCost && (
            <span className="font-mono text-xs text-muted-fg">{cost} ₽</span>
          )}
          <Badge tone="orange">{MARKETPLACE_LABEL[integration.marketplace]}</Badge>
        </div>
      </div>

      {/* Row 4: fact_views if available */}
      {integration.fact_views != null && integration.fact_views > 0 && (
        <div className="mt-1.5 flex items-center gap-1 text-xs text-muted-fg">
          <span>👁</span>
          <span>охват: {formatViews(integration.fact_views)}</span>
        </div>
      )}
    </button>
  );
}

export default KanbanCard;
