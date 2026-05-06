import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

interface PageHeaderProps {
  title: string;
  sub?: string;
  actions?: ReactNode;
  className?: string;
}

export function PageHeader({ title, sub, actions, className }: PageHeaderProps) {
  return (
    <header
      className={cn(
        'mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between',
        className,
      )}
    >
      <div>
        <h1 className="font-display text-3xl font-bold text-fg">{title}</h1>
        {sub && <p className="mt-1 text-sm text-muted-fg">{sub}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </header>
  );
}

export type { PageHeaderProps };
