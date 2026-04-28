import { forwardRef, type TextareaHTMLAttributes } from 'react';
import { cn } from '@/lib/cn';

export type TextareaProps = TextareaHTMLAttributes<HTMLTextAreaElement>;

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, rows = 3, ...rest }, ref) => (
    <textarea
      ref={ref}
      rows={rows}
      className={cn(
        'w-full rounded-md border border-border bg-card px-3 py-2 text-sm',
        'focus:border-primary-muted focus:outline-none focus:ring-2 focus:ring-primary/20',
        'placeholder:text-muted-fg resize-y',
        className,
      )}
      {...rest}
    />
  ),
);
Textarea.displayName = 'Textarea';
