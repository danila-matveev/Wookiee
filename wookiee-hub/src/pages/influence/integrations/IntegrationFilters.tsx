import { useRef, useState } from 'react';
import { cn } from '@/lib/utils';
import { STAGES, STAGE_LABELS, type Channel, type Marketplace } from '@/api/crm/integrations';

// ─── Public types ─────────────────────────────────────────────────────────────

export interface IntegrationFilterValue {
  q?: string;
  channel?: string;
  stage_in?: string[];
  date_from?: string;
  date_to?: string;
  marketplace?: string;
}

export interface IntegrationFiltersProps {
  value: IntegrationFilterValue;
  onChange: (v: IntegrationFilterValue) => void;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const CHANNEL_LABELS: Record<Channel, string> = {
  instagram: 'IG',
  telegram: 'TG',
  tiktok: 'TikTok',
  youtube: 'YT',
  vk: 'VK',
  rutube: 'RT',
};

const CHANNELS = Object.keys(CHANNEL_LABELS) as Channel[];

const MARKETPLACE_LABELS: Record<Marketplace, string> = {
  wb: 'WB',
  ozon: 'OZON',
  both: 'Оба',
};

const MARKETPLACES = Object.keys(MARKETPLACE_LABELS) as Marketplace[];

// ─── Helper styles ────────────────────────────────────────────────────────────

function pillCn(active: boolean) {
  return cn(
    'text-xs px-2.5 py-1 rounded-full border transition-colors cursor-pointer',
    active
      ? 'bg-primary text-primary-fg border-primary'
      : 'border-border text-muted-fg hover:border-primary/50',
  );
}

// ─── Component ────────────────────────────────────────────────────────────────

export function IntegrationFilters({ value, onChange }: IntegrationFiltersProps) {
  // Local search state — flushed to parent on Enter / blur
  const [localQ, setLocalQ] = useState(value.q ?? '');
  const inputRef = useRef<HTMLInputElement>(null);

  function flushQ() {
    const trimmed = localQ.trim();
    if (trimmed !== (value.q ?? '')) {
      onChange({ ...value, q: trimmed || undefined });
    }
  }

  function toggleStage(stage: string) {
    const current = value.stage_in ?? [];
    const next = current.includes(stage)
      ? current.filter((s) => s !== stage)
      : [...current, stage];
    onChange({ ...value, stage_in: next.length ? next : undefined });
  }

  function setChannel(ch: string) {
    onChange({ ...value, channel: value.channel === ch ? undefined : ch });
  }

  function setMarketplace(mp: string) {
    onChange({ ...value, marketplace: value.marketplace === mp ? undefined : mp });
  }

  function setDate(key: 'date_from' | 'date_to', val: string) {
    onChange({ ...value, [key]: val || undefined });
  }

  const isAnyActive =
    !!value.q ||
    !!value.channel ||
    !!(value.stage_in?.length) ||
    !!value.date_from ||
    !!value.date_to ||
    !!value.marketplace;

  function reset() {
    setLocalQ('');
    onChange({});
  }

  return (
    <div className="flex flex-col gap-2 py-3">
      {/* Row 1: search, dates, marketplace, reset */}
      <div className="flex flex-wrap items-center gap-2">
        {/* Search */}
        <input
          ref={inputRef}
          type="search"
          placeholder="Поиск по блогеру…"
          value={localQ}
          onChange={(e) => setLocalQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              flushQ();
              inputRef.current?.blur();
            }
          }}
          onBlur={flushQ}
          className={cn(
            'w-48 rounded-md border border-border bg-card px-3 py-1.5 text-sm',
            'focus:border-primary-muted focus:outline-none focus:ring-2 focus:ring-primary/20',
            'placeholder:text-muted-fg',
          )}
        />

        {/* Date from */}
        <input
          type="date"
          value={value.date_from ?? ''}
          onChange={(e) => setDate('date_from', e.target.value)}
          className={cn(
            'rounded-md border border-border bg-card px-3 py-1.5 text-sm',
            'focus:border-primary-muted focus:outline-none focus:ring-2 focus:ring-primary/20',
            'text-muted-fg',
          )}
        />

        {/* Date to */}
        <input
          type="date"
          value={value.date_to ?? ''}
          onChange={(e) => setDate('date_to', e.target.value)}
          className={cn(
            'rounded-md border border-border bg-card px-3 py-1.5 text-sm',
            'focus:border-primary-muted focus:outline-none focus:ring-2 focus:ring-primary/20',
            'text-muted-fg',
          )}
        />

        {/* Marketplace pills */}
        <div className="flex items-center gap-1">
          {MARKETPLACES.map((mp) => (
            <button
              key={mp}
              type="button"
              onClick={() => setMarketplace(mp)}
              className={pillCn(value.marketplace === mp)}
            >
              {MARKETPLACE_LABELS[mp]}
            </button>
          ))}
        </div>

        {/* Reset */}
        {isAnyActive && (
          <button
            type="button"
            onClick={reset}
            className="text-xs px-2.5 py-1 rounded-full border border-border text-muted-fg hover:border-destructive/50 hover:text-destructive transition-colors cursor-pointer"
          >
            Сбросить
          </button>
        )}
      </div>

      {/* Row 2: channel pills, stage pills */}
      <div className="flex flex-wrap items-center gap-1.5">
        {/* Channel pills */}
        <span className="text-xs text-muted-fg mr-1">Канал:</span>
        {CHANNELS.map((ch) => (
          <button
            key={ch}
            type="button"
            onClick={() => setChannel(ch)}
            className={pillCn(value.channel === ch)}
          >
            {CHANNEL_LABELS[ch]}
          </button>
        ))}

        <span className="mx-2 text-border">|</span>

        {/* Stage pills */}
        <span className="text-xs text-muted-fg mr-1">Стадия:</span>
        {STAGES.map((stage) => (
          <button
            key={stage}
            type="button"
            onClick={() => toggleStage(stage)}
            className={pillCn(!!(value.stage_in?.includes(stage)))}
          >
            {STAGE_LABELS[stage]}
          </button>
        ))}
      </div>
    </div>
  );
}
