import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

interface EmptyStateProps {
  title: string;
  description?: ReactNode;
  icon?: ReactNode;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({ title, description, icon, action, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center text-center gap-3 rounded-lg border border-dashed border-border-strong bg-card px-6 py-10',
        className,
      )}
    >
      {icon && <div className="text-muted-fg">{icon}</div>}
      <div className="font-display text-base font-semibold text-fg">{title}</div>
      {description && <p className="max-w-md text-sm text-muted-fg">{description}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

export type { EmptyStateProps };
