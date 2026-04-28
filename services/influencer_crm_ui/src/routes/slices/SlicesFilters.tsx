import { useId } from 'react';
import type { Marketplace } from '@/api/integrations';
import { FilterPill } from '@/ui/FilterPill';
import { Input } from '@/ui/Input';

export interface SlicesFilterValue {
  marketplace?: Marketplace;
  date_from?: string;
  date_to?: string;
  marketer_id?: number;
}

interface Props {
  value: SlicesFilterValue;
  onChange: (next: SlicesFilterValue) => void;
}

interface MarketplaceOption {
  key: Marketplace | undefined;
  label: string;
}

// Note on marketplace="both": on the BFF, this is a value used for the integration row itself
// (campaign hits both channels), not a query filter that means "any". For "any" we send
// undefined. We expose only wb / ozon as user-selectable filters; the row's own "both" value
// will appear in the result column verbatim.
const marketplaces: MarketplaceOption[] = [
  { key: undefined, label: 'Все' },
  { key: 'wb', label: 'WB' },
  { key: 'ozon', label: 'OZON' },
];

export function SlicesFilters({ value, onChange }: Props) {
  const dateFromId = useId();
  const dateToId = useId();
  const marketerId = useId();

  function setMarketerId(raw: string) {
    const parsed = raw.trim() === '' ? undefined : Number.parseInt(raw, 10);
    const next: SlicesFilterValue = {
      ...value,
      marketer_id: Number.isFinite(parsed) ? (parsed as number) : undefined,
    };
    onChange(next);
  }

  return (
    <div className="bg-card border border-border rounded-lg shadow-warm px-3.5 py-3 mb-5 flex flex-wrap items-center gap-2.5">
      <span className="text-[11px] uppercase tracking-wider text-muted-fg font-semibold">
        Маркетплейс
      </span>
      {marketplaces.map((m) => (
        <FilterPill
          key={m.label}
          active={value.marketplace === m.key}
          onClick={() => onChange({ ...value, marketplace: m.key })}
        >
          {m.label}
        </FilterPill>
      ))}

      <div className="ml-2 flex items-center gap-1.5">
        <label
          htmlFor={dateFromId}
          className="text-[11px] uppercase tracking-wider text-muted-fg font-semibold"
        >
          С
        </label>
        <Input
          id={dateFromId}
          type="date"
          className="max-w-[160px]"
          value={value.date_from ?? ''}
          onChange={(e) => onChange({ ...value, date_from: e.target.value || undefined })}
        />
        <label
          htmlFor={dateToId}
          className="text-[11px] uppercase tracking-wider text-muted-fg font-semibold"
        >
          по
        </label>
        <Input
          id={dateToId}
          type="date"
          className="max-w-[160px]"
          value={value.date_to ?? ''}
          onChange={(e) => onChange({ ...value, date_to: e.target.value || undefined })}
        />
      </div>

      <div className="ml-auto flex items-center gap-1.5">
        <label
          htmlFor={marketerId}
          className="text-[11px] uppercase tracking-wider text-muted-fg font-semibold"
        >
          Маркетолог ID
        </label>
        <Input
          id={marketerId}
          type="number"
          inputMode="numeric"
          className="max-w-[120px]"
          placeholder="—"
          value={value.marketer_id ?? ''}
          onChange={(e) => setMarketerId(e.target.value)}
        />
      </div>
    </div>
  );
}
