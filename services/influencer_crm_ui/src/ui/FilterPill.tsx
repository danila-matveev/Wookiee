import { type ButtonHTMLAttributes, forwardRef } from 'react';
import { cn } from '@/lib/cn';

interface FilterPillProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  active?: boolean;
  solid?: boolean;
}

export const FilterPill = forwardRef<HTMLButtonElement, FilterPillProps>(
  ({ active, solid, className, children, ...rest }, ref) => (
    <button
      ref={ref}
      type={rest.type ?? 'button'}
      aria-pressed={active}
      className={cn(
        'inline-flex items-center gap-1 rounded-full border px-3 py-1.5 text-xs font-medium',
        'transition-colors duration-200 cursor-pointer',
        solid
          ? 'bg-primary text-white border-primary hover:bg-primary-hover'
          : active
            ? 'bg-primary-light border-primary-muted text-primary-hover'
            : 'bg-muted border-border text-fg hover:bg-primary-light',
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  ),
);
FilterPill.displayName = 'FilterPill';

export type { FilterPillProps };
