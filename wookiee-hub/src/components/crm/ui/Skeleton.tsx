import type { HTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

export type SkeletonProps = HTMLAttributes<HTMLDivElement>;

/**
 * Pulse skeleton placeholder.
 * The global `prefers-reduced-motion` rule in styles/tokens.css already
 * collapses animation duration to 0.01ms when the user requests reduced motion,
 * so the Tailwind `animate-pulse` is automatically respected.
 */
export function Skeleton({ className, ...rest }: SkeletonProps) {
  return (
    <div
      aria-hidden="true"
      className={cn('animate-pulse rounded-md bg-muted', className)}
      {...rest}
    />
  );
}
