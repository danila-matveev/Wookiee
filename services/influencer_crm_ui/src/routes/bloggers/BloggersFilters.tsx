import { useId } from 'react';
import type { BloggerListParams, BloggerStatus } from '@/api/bloggers';
import { FilterPill } from '@/ui/FilterPill';
import { Input } from '@/ui/Input';

export type BloggersFilterValue = Pick<
  BloggerListParams,
  'status' | 'q' | 'marketer_id' | 'tag_id'
>;

interface Props {
  value: BloggersFilterValue;
  onChange: (next: BloggersFilterValue) => void;
}

interface StatusOption {
  key: BloggerStatus | undefined;
  label: string;
}

const statuses: StatusOption[] = [
  { key: undefined, label: 'Все' },
  { key: 'active', label: 'Активные' },
  { key: 'paused', label: 'На паузе' },
  { key: 'new', label: 'Новые' },
];

export function BloggersFilters({ value, onChange }: Props) {
  const searchId = useId();
  return (
    <div className="bg-card border border-border rounded-lg shadow-warm px-3.5 py-3 mb-5 flex items-center gap-2.5 flex-wrap">
      <span className="text-[11px] uppercase tracking-wider text-muted-fg font-semibold">
        Статус
      </span>
      {statuses.map((s) => (
        <FilterPill
          key={s.label}
          active={value.status === s.key}
          onClick={() => onChange({ ...value, status: s.key })}
        >
          {s.label}
        </FilterPill>
      ))}
      <label htmlFor={searchId} className="sr-only">
        Поиск блогеров
      </label>
      <Input
        id={searchId}
        className="ml-auto max-w-xs"
        placeholder="Поиск по handle / имени"
        value={value.q ?? ''}
        onChange={(e) => onChange({ ...value, q: e.target.value || undefined })}
      />
    </div>
  );
}
