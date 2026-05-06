import { useMemo } from 'react';
import type { IntegrationOut, Stage } from '@/api/crm/integrations';
import { cn } from '@/lib/utils';
import { type PlatformChannel, PlatformPill } from '@/components/crm/ui/PlatformPill';

const WEEKDAYS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];
const MAX_VISIBLE_EVENTS = 3;

export function getMonthCells(year: number, month: number): Date[] {
  const first = new Date(year, month, 1);
  const startWeekday = (first.getDay() + 6) % 7; // Mon=0..Sun=6
  return Array.from({ length: 42 }, (_, i) => {
    return new Date(year, month, 1 - startWeekday + i);
  });
}

export function toIsoDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function stageMarkerClass(stage: Stage): string {
  switch (stage) {
    case 'завершено':
      return 'bg-success';
    case 'запланировано':
    case 'аналитика':
      return 'bg-warning';
    case 'переговоры':
    case 'согласовано':
    case 'отправка_комплекта':
    case 'контент':
      return 'bg-primary';
    default:
      return 'bg-muted-fg';
  }
}

function asPlatformChannel(channel: IntegrationOut['channel']): PlatformChannel {
  return channel === 'rutube' ? 'youtube' : channel;
}

interface CalendarMonthGridProps {
  monthDate: Date;
  integrations: IntegrationOut[];
  onEventClick: (id: number) => void;
  onCellClick: (isoDate: string) => void;
  today?: Date;
}

export function CalendarMonthGrid({
  monthDate,
  integrations,
  onEventClick,
  onCellClick,
  today: todayProp,
}: CalendarMonthGridProps) {
  const today = todayProp ?? new Date();
  const todayIso = toIsoDate(today);
  const currentMonth = monthDate.getMonth();

  const cells = useMemo(
    () => getMonthCells(monthDate.getFullYear(), monthDate.getMonth()),
    [monthDate],
  );

  const eventsByDate = useMemo(() => {
    const map = new Map<string, IntegrationOut[]>();
    for (const it of integrations) {
      const key = it.publish_date;
      const bucket = map.get(key);
      if (bucket) bucket.push(it);
      else map.set(key, [it]);
    }
    return map;
  }, [integrations]);

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-card">
      {/* Weekday header */}
      <div className="grid grid-cols-7 border-b border-border bg-muted/40" aria-hidden="true">
        {WEEKDAYS.map((w) => (
          <div key={w} className="px-2 py-2 text-center text-xs font-semibold text-muted-fg">
            {w}
          </div>
        ))}
      </div>

      {/* biome-ignore lint/a11y/useSemanticElements: ARIA grid is the correct role for a calendar widget */}
      <div role="grid" aria-label="Календарь публикаций" className="grid grid-cols-7">
        {Array.from({ length: 6 }, (_, weekIdx) => (
          // biome-ignore lint/a11y/useSemanticElements: ARIA row is required as gridcell parent.
          // biome-ignore lint/suspicious/noArrayIndexKey: weekIdx is stable for the visible 6-row layout.
          // biome-ignore lint/a11y/useFocusableInteractive: row is a non-interactive landmark; gridcell children carry tabIndex.
          <div key={`week-${weekIdx}`} role="row" className="contents">
            {cells.slice(weekIdx * 7, weekIdx * 7 + 7).map((date, colIdx) => {
              const idx = weekIdx * 7 + colIdx;
              const iso = toIsoDate(date);
              const inMonth = date.getMonth() === currentMonth;
              const isToday = iso === todayIso;
              const events = eventsByDate.get(iso) ?? [];
              const visible = events.slice(0, MAX_VISIBLE_EVENTS);
              const overflow = events.length - visible.length;
              const isLastCol = (idx + 1) % 7 === 0;
              const isLastRow = idx >= 35;

              return (
                // biome-ignore lint/a11y/useSemanticElements: ARIA gridcell is required by the calendar contract.
                <div
                  key={iso}
                  role="gridcell"
                  className={cn(
                    'flex min-h-24 cursor-pointer flex-col gap-1 px-2 py-1.5 text-left',
                    'transition-colors hover:bg-primary-light/40 focus-within:bg-primary-light',
                    !isLastCol && 'border-r border-border',
                    !isLastRow && 'border-b border-border',
                    !inMonth && 'bg-muted/30',
                    isToday && 'bg-primary-light',
                  )}
                  onClick={() => onCellClick(iso)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      onCellClick(iso);
                    }
                  }}
                  tabIndex={0}
                  aria-label={`${date.getDate()} ${date.toLocaleDateString('ru-RU', { month: 'long' })}${isToday ? ' (сегодня)' : ''}`}
                >
                  <span
                    className={cn(
                      'text-xs font-semibold',
                      inMonth ? 'text-fg' : 'text-muted-fg/60',
                      isToday && 'text-primary-hover',
                    )}
                  >
                    {date.getDate()}
                  </span>
                  <div className="flex flex-col gap-1">
                    {visible.map((ev) => (
                      <button
                        key={ev.id}
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          onEventClick(ev.id);
                        }}
                        onKeyDown={(e) => e.stopPropagation()}
                        className="flex items-center gap-1.5 rounded-md border border-border bg-card px-1.5 py-1 text-left text-xs hover:border-primary-muted hover:bg-primary-light"
                      >
                        <span
                          className={cn(
                            'size-1.5 shrink-0 rounded-full',
                            stageMarkerClass(ev.stage),
                          )}
                          aria-hidden="true"
                        />
                        <PlatformPill
                          channel={asPlatformChannel(ev.channel)}
                          className="!size-[14px] !text-[7px]"
                        />
                        <span className="truncate text-muted-fg">Блогер #{ev.blogger_id}</span>
                      </button>
                    ))}
                    {overflow > 0 && (
                      <span className="self-start rounded-full bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-fg">
                        +{overflow}
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

export default CalendarMonthGrid;
