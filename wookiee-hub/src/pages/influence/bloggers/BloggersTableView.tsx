import { useRef } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import type { BloggerSummaryOut, BloggerSummaryParams } from '@/api/crm/bloggers';
import { useBloggersSummary } from '@/hooks/crm/use-bloggers';

function handleToColor(handle: string): string {
  let hash = 0;
  for (let i = 0; i < handle.length; i++) {
    hash = handle.charCodeAt(i) + ((hash << 5) - hash);
  }
  const colors = ['#6366f1', '#8b5cf6', '#ec4899', '#f97316', '#14b8a6', '#3b82f6', '#84cc16'];
  return colors[Math.abs(hash) % colors.length];
}

const PLATFORM_SHORT: Record<string, string> = {
  instagram: 'IG',
  telegram: 'TG',
  tiktok: 'TT',
  youtube: 'YT',
  vk: 'VK',
  rutube: 'RT',
};

const STATUS_LABEL: Record<string, string> = {
  active: 'Активен',
  in_progress: 'В работе',
  new: 'Новый',
  paused: 'Пауза',
  inactive: 'Неактив',
};

const STATUS_BG: Record<string, string> = {
  active: 'bg-green-100 text-green-700',
  in_progress: 'bg-blue-100 text-blue-700',
  new: 'bg-amber-100 text-amber-700',
  paused: 'bg-gray-100 text-gray-500',
  inactive: 'bg-gray-100 text-gray-400',
};

interface Props {
  params: BloggerSummaryParams;
  onRowClick: (id: number) => void;
}

export function BloggersTableView({ params, onRowClick }: Props) {
  const { data, isLoading } = useBloggersSummary(params);
  const items = data?.items ?? [];

  const parentRef = useRef<HTMLDivElement>(null);
  const rowVirtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 52,
    overscan: 10,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-48 text-muted-fg text-sm">
        Загрузка...
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-muted-fg text-sm">
        Нет блогеров
      </div>
    );
  }

  const COLS = [
    { key: 'blogger', label: 'Блогер', cls: 'min-w-44 max-w-56' },
    { key: 'channels', label: 'Каналы', cls: 'w-36' },
    { key: 'total', label: 'Инт-ций', cls: 'w-20 text-right' },
    { key: 'done', label: 'Выпол.', cls: 'w-20 text-right' },
    { key: 'cpm', label: 'Ср. CPM', cls: 'w-28 text-right' },
    { key: 'story', label: 'Story ₽', cls: 'w-24 text-right' },
    { key: 'reels', label: 'Reels ₽', cls: 'w-24 text-right' },
    { key: 'status', label: 'Статус', cls: 'w-24' },
    { key: 'last', label: 'Посл. инт.', cls: 'w-24' },
  ] as const;

  const renderCell = (key: string, row: BloggerSummaryOut): React.ReactNode => {
    switch (key) {
      case 'blogger':
        return (
          <div className="flex items-center gap-2 overflow-hidden">
            <div
              className="size-7 rounded-full flex items-center justify-center text-xs font-bold text-white shrink-0"
              style={{ backgroundColor: handleToColor(row.display_handle) }}
            >
              {row.display_handle[0]?.toUpperCase() ?? '?'}
            </div>
            <div className="overflow-hidden">
              <div className="truncate text-sm font-medium">{row.display_handle}</div>
              {row.real_name && (
                <div className="truncate text-xs text-muted-fg">{row.real_name}</div>
              )}
            </div>
          </div>
        );
      case 'channels':
        return (
          <div className="flex flex-wrap gap-1">
            {row.channels.slice(0, 4).map((ch) =>
              ch.url ? (
                <a
                  key={ch.id}
                  href={ch.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-primary font-medium hover:underline"
                  onClick={(e) => e.stopPropagation()}
                >
                  {PLATFORM_SHORT[ch.channel] ?? ch.channel.toUpperCase()}
                </a>
              ) : (
                <span
                  key={ch.id}
                  className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-fg font-medium"
                >
                  {PLATFORM_SHORT[ch.channel] ?? ch.channel.toUpperCase()}
                </span>
              ),
            )}
            {row.channels.length > 4 && (
              <span className="text-[10px] text-muted-fg">+{row.channels.length - 4}</span>
            )}
          </div>
        );
      case 'total':
        return <span className="tabular-nums text-sm">{row.integrations_count}</span>;
      case 'done':
        return <span className="tabular-nums text-sm">{row.integrations_done}</span>;
      case 'cpm':
        return (
          <span className="tabular-nums text-sm">
            {row.avg_cpm_fact
              ? `${parseFloat(row.avg_cpm_fact).toLocaleString('ru-RU')} ₽`
              : '—'}
          </span>
        );
      case 'story':
        return (
          <span className="tabular-nums text-sm">
            {row.price_story_default
              ? `${parseFloat(row.price_story_default).toLocaleString('ru-RU')}`
              : '—'}
          </span>
        );
      case 'reels':
        return (
          <span className="tabular-nums text-sm">
            {row.price_reels_default
              ? `${parseFloat(row.price_reels_default).toLocaleString('ru-RU')}`
              : '—'}
          </span>
        );
      case 'status':
        return (
          <span
            className={`text-xs px-1.5 py-0.5 rounded font-medium ${STATUS_BG[row.status] ?? 'bg-muted text-muted-fg'}`}
          >
            {STATUS_LABEL[row.status] ?? row.status}
          </span>
        );
      case 'last':
        return (
          <span className="text-xs text-muted-fg tabular-nums">
            {row.last_integration_at
              ? new Date(row.last_integration_at).toLocaleDateString('ru-RU', {
                  day: '2-digit',
                  month: '2-digit',
                  year: '2-digit',
                })
              : '—'}
          </span>
        );
      default:
        return null;
    }
  };

  return (
    <div className="rounded-lg border border-border bg-card overflow-hidden">
      <div className="flex border-b border-border bg-muted/40 px-3 py-2 text-xs font-medium text-muted-fg select-none">
        {COLS.map((col) => (
          <div key={col.key} className={`${col.cls} shrink-0 pr-3`}>
            {col.label}
          </div>
        ))}
      </div>
      <div ref={parentRef} className="overflow-auto" style={{ maxHeight: 'calc(100vh - 280px)' }}>
        <div style={{ height: `${rowVirtualizer.getTotalSize()}px`, position: 'relative' }}>
          {rowVirtualizer.getVirtualItems().map((vr) => {
            const row = items[vr.index];
            return (
              <div
                key={row.id}
                role="row"
                tabIndex={0}
                className="absolute left-0 right-0 flex items-center px-3 border-b border-border/50 hover:bg-muted/30 cursor-pointer transition-colors"
                style={{ top: vr.start, height: vr.size }}
                onClick={() => onRowClick(row.id)}
                onKeyDown={(e) => e.key === 'Enter' && onRowClick(row.id)}
              >
                {COLS.map((col) => (
                  <div key={col.key} className={`${col.cls} shrink-0 overflow-hidden pr-3`}>
                    {renderCell(col.key, row)}
                  </div>
                ))}
              </div>
            );
          })}
        </div>
      </div>
      <div className="px-3 py-2 text-xs text-muted-fg border-t border-border bg-muted/20">
        {data?.total ?? 0} блогеров · CPM взвешенный по всем интеграциям
      </div>
    </div>
  );
}
