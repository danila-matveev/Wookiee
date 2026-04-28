import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';

type Accent = 'primary' | 'info' | 'success' | 'pink' | 'blue';
type ChangeDirection = 'pos' | 'neg' | 'neu';

const accentValueClass: Record<Accent, string> = {
  primary: 'text-primary',
  info: 'text-info',
  success: 'text-success',
  pink: 'text-pink',
  blue: 'text-blue',
};

const accentDotClass: Record<Accent, string> = {
  primary: 'bg-primary',
  info: 'bg-info',
  success: 'bg-success',
  pink: 'bg-pink',
  blue: 'bg-blue',
};

const changeClass: Record<ChangeDirection, string> = {
  pos: 'text-success',
  neg: 'text-danger',
  neu: 'text-muted-fg',
};

interface KpiCardProps {
  title: string;
  value: ReactNode;
  change?: { label: string; direction: ChangeDirection };
  accent?: Accent;
  hint?: ReactNode;
  className?: string;
}

export function KpiCard({
  title,
  value,
  change,
  accent = 'primary',
  hint,
  className,
}: KpiCardProps) {
  return (
    <div
      className={cn(
        'rounded-lg border border-border-strong bg-card shadow-warm p-5',
        'transition-all duration-200 hover:shadow-warm-lg hover:-translate-y-0.5',
        className,
      )}
    >
      <div className="flex items-start justify-between">
        <div className="text-xs font-medium text-muted-fg mb-1.5">{title}</div>
        <span
          aria-hidden="true"
          className={cn('size-2 rounded-full mt-1.5', accentDotClass[accent])}
        />
      </div>
      <div
        className={cn(
          'font-mono text-2xl font-bold leading-tight tracking-tight',
          accentValueClass[accent],
        )}
      >
        {value}
      </div>
      {change && (
        <div className={cn('font-mono text-[11px] mt-1', changeClass[change.direction])}>
          {change.label}
        </div>
      )}
      {hint && <div className="text-[11px] text-muted-fg mt-1">{hint}</div>}
    </div>
  );
}

export type { KpiCardProps };
