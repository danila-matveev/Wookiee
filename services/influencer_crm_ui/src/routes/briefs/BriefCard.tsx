import type { BriefOut } from '@/api/briefs';
import { cn } from '@/lib/cn';
import { Avatar } from '@/ui/Avatar';
import { Badge } from '@/ui/Badge';

function formatDate(iso: string | null | undefined): string | null {
  if (!iso) return null;
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

function formatBudget(value: string | null | undefined): string | null {
  if (!value) return null;
  const num = Number(value);
  if (!Number.isFinite(num) || num === 0) return null;
  return `${new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(num)} ₽`;
}

interface BriefCardProps {
  brief: BriefOut;
  onOpen?: (id: number) => void;
}

export function BriefCard({ brief, onOpen }: BriefCardProps) {
  const handleLabel =
    brief.blogger_handle ?? (brief.blogger_id ? `Блогер #${brief.blogger_id}` : 'Без блогера');
  const dateLabel = formatDate(brief.scheduled_at);
  const budgetLabel = formatBudget(brief.budget);

  return (
    <button
      type="button"
      onClick={() => onOpen?.(brief.id)}
      data-testid={`brief-card-${brief.id}`}
      className={cn(
        'block w-full text-left',
        'cursor-pointer rounded-lg border border-border bg-surface p-3 shadow-sm',
        'hover:border-primary-light hover:shadow',
        'focus:outline-none focus:ring-2 focus:ring-primary/30',
      )}
    >
      <div className="flex items-center gap-2">
        <Avatar size="xs" name={handleLabel} />
        <span className="font-display text-sm font-semibold text-fg truncate">{handleLabel}</span>
        <Badge tone="secondary" className="ml-auto">
          v{brief.current_version}
        </Badge>
      </div>

      <p className="mt-2 line-clamp-2 text-sm text-fg">{brief.title}</p>

      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        {dateLabel && <Badge tone="info">{dateLabel}</Badge>}
        {budgetLabel && <Badge tone="orange">{budgetLabel}</Badge>}
        {brief.integration_id != null && <Badge tone="secondary">№{brief.integration_id}</Badge>}
      </div>
    </button>
  );
}

export default BriefCard;
