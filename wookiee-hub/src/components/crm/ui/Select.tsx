import { ChevronDown } from 'lucide-react';
import { forwardRef, type SelectHTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

export type SelectProps = SelectHTMLAttributes<HTMLSelectElement>;

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, children, ...rest }, ref) => (
    <span className="relative inline-block w-full">
      <select
        ref={ref}
        className={cn(
          'w-full appearance-none rounded-md border border-border bg-card px-3 py-2 pr-9 text-sm',
          'focus:border-primary-muted focus:outline-none focus:ring-2 focus:ring-primary/20',
          'disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer',
          className,
        )}
        {...rest}
      >
        {children}
      </select>
      <ChevronDown
        aria-hidden="true"
        className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 size-4 text-muted-fg"
      />
    </span>
  ),
);
Select.displayName = 'Select';
