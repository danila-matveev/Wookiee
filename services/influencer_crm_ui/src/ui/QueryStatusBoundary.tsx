import type { ReactNode } from 'react';
import { EmptyState } from './EmptyState';
import { Skeleton } from './Skeleton';

interface Props {
  isLoading: boolean;
  error: unknown;
  isEmpty?: boolean;
  loadingFallback?: ReactNode;
  emptyTitle?: string;
  emptyDescription?: string;
  children: ReactNode;
}

/**
 * Unified loading/error/empty wrapper for list-based screens.
 *
 * - `isLoading` → render `loadingFallback` (defaults to a tall Skeleton).
 * - `error`     → render an inline error card with the message.
 * - `isEmpty`   → render an EmptyState with `emptyTitle` / `emptyDescription`.
 * - otherwise   → render `children`.
 *
 * Replaces the ad-hoc `isLoading ? <Skeleton/> : items.length === 0 ? <EmptyState/> : ...`
 * ladders that lived in every screen and silently disagreed about error UX.
 */
export function QueryStatusBoundary({
  isLoading,
  error,
  isEmpty,
  loadingFallback,
  emptyTitle = 'Пусто',
  emptyDescription = 'Снимите фильтры или добавьте первую запись.',
  children,
}: Props) {
  if (isLoading) return <>{loadingFallback ?? <Skeleton className="h-96" />}</>;
  if (error) {
    const msg = error instanceof Error ? error.message : 'Что-то пошло не так';
    return (
      <div role="alert" className="rounded-lg border border-danger/30 bg-danger/5 p-6">
        <h3 className="font-semibold text-danger">Ошибка загрузки</h3>
        <p className="text-sm text-muted-fg mt-1">{msg}</p>
      </div>
    );
  }
  if (isEmpty) return <EmptyState title={emptyTitle} description={emptyDescription} />;
  return <>{children}</>;
}

export default QueryStatusBoundary;
