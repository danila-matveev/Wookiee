import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';

type Tone = 'success' | 'warning' | 'info' | 'orange' | 'pink' | 'secondary' | 'danger';

const tones: Record<Tone, string> = {
  success: 'bg-success/10 text-success',
  warning: 'bg-warning/10 text-warning',
  info: 'bg-info/10 text-info',
  orange: 'bg-primary-light text-primary-hover',
  pink: 'bg-pink/10 text-pink',
  secondary: 'bg-muted text-muted-fg border border-border',
  danger: 'bg-danger/10 text-danger',
};

interface BadgeProps {
  tone?: Tone;
  children: ReactNode;
  className?: string;
}

export function Badge({ tone = 'secondary', children, className }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-semibold',
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

export type { BadgeProps };
