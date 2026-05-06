import { forwardRef, type InputHTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

export type InputProps = InputHTMLAttributes<HTMLInputElement>;

export const Input = forwardRef<HTMLInputElement, InputProps>(({ className, ...rest }, ref) => (
  <input
    ref={ref}
    className={cn(
      'w-full rounded-md border border-border bg-card px-3 py-2 text-sm',
      'focus:border-primary-muted focus:outline-none focus:ring-2 focus:ring-primary/20',
      'placeholder:text-muted-fg',
      className,
    )}
    {...rest}
  />
));
Input.displayName = 'Input';
