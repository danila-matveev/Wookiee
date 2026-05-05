import type { ReactNode } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import type { BloggerOut, BloggerStatus } from '@/api/bloggers';
import type { IntegrationOut, Stage } from '@/api/integrations';
import { STAGE_LABELS } from '@/api/integrations';
import { useSearch } from '@/hooks/use-search';
import { PageHeader } from '@/layout/PageHeader';
import { Avatar } from '@/ui/Avatar';
import { Badge, type BadgeProps } from '@/ui/Badge';
import { EmptyState } from '@/ui/EmptyState';
import { QueryStatusBoundary } from '@/ui/QueryStatusBoundary';
import { Tabs } from '@/ui/Tabs';

const STATUS_TONE: Record<BloggerStatus, NonNullable<BadgeProps['tone']>> = {
  active: 'success',
  paused: 'warning',
  in_progress: 'info',
  new: 'secondary',
};

const STATUS_LABEL: Record<BloggerStatus, string> = {
  active: 'Активный',
  paused: 'На паузе',
  in_progress: 'В работе',
  new: 'Новый',
};

const STAGE_TONE: Record<Stage, NonNullable<BadgeProps['tone']>> = {
  переговоры: 'secondary',
  согласовано: 'info',
  отправка_комплекта: 'info',
  контент: 'info',
  запланировано: 'warning',
  аналитика: 'orange',
  завершено: 'success',
  архив: 'secondary',
};

function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' });
  } catch {
    return iso;
  }
}

function formatCost(value: string | null): string {
  if (!value) return '—';
  const num = Number(value);
  if (!Number.isFinite(num) || num === 0) return '—';
  return `${new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(num)} ₽`;
}

function BloggerResultCard({ blogger }: { blogger: BloggerOut }) {
  const displayName = blogger.real_name ?? blogger.display_handle;
  return (
    <Link
      to={`/bloggers?open=${blogger.id}`}
      data-testid={`search-result-blogger-${blogger.id}`}
      className="flex items-center gap-3 rounded-lg border border-border bg-card px-4 py-3 shadow-sm transition-colors duration-150 hover:border-primary-light hover:bg-bg-warm"
    >
      <Avatar name={displayName} />
      <div className="min-w-0 flex-1">
        <div className="font-semibold text-sm text-fg truncate">{displayName}</div>
        <div className="text-xs text-muted-fg truncate">@{blogger.display_handle}</div>
      </div>
      <Badge tone={STATUS_TONE[blogger.status]}>{STATUS_LABEL[blogger.status]}</Badge>
    </Link>
  );
}

function IntegrationResultCard({ integration }: { integration: IntegrationOut }) {
  const handleLabel = integration.blogger_handle ?? `Блогер #${integration.blogger_id}`;
  return (
    <Link
      to={`/bloggers?open=${integration.blogger_id}`}
      data-testid={`search-result-integration-${integration.id}`}
      className="flex items-center gap-3 rounded-lg border border-border bg-card px-4 py-3 shadow-sm transition-colors duration-150 hover:border-primary-light hover:bg-bg-warm"
    >
      <Avatar size="xs" name={handleLabel} />
      <div className="min-w-0 flex-1">
        <div className="font-semibold text-sm text-fg truncate">{handleLabel}</div>
        <div className="text-xs text-muted-fg truncate">
          {formatDate(integration.publish_date)} · {formatCost(integration.total_cost)}
        </div>
      </div>
      <Badge tone={STAGE_TONE[integration.stage]}>{STAGE_LABELS[integration.stage]}</Badge>
    </Link>
  );
}

function ResultsStack({ children }: { children: ReactNode }) {
  return <div className="flex flex-col gap-2">{children}</div>;
}

export function SearchPage() {
  const [params] = useSearchParams();
  const q = params.get('q') ?? '';
  const { data, isLoading, error } = useSearch(q);

  const bloggers = data?.bloggers ?? [];
  const integrations = data?.integrations ?? [];
  const total = bloggers.length + integrations.length;

  const sub = q
    ? `по запросу «${q}»`
    : 'Введите запрос в поиске наверху, чтобы найти блогеров и интеграции.';

  // Empty-query state: don't kick the QueryStatusBoundary at all — `useSearch`
  // is disabled until q has 2+ chars, so isLoading would never flip and the
  // boundary's empty branch would conflate "type something" with "no results".
  if (!q) {
    return (
      <>
        <PageHeader title="Поиск" sub={sub} />
        <EmptyState
          title="Введите запрос в поиске наверху"
          description="Глобальный поиск по блогерам и интеграциям. Минимум 2 символа."
        />
      </>
    );
  }

  const allContent = (
    <ResultsStack>
      {bloggers.map((b) => (
        <BloggerResultCard key={`b-${b.id}`} blogger={b} />
      ))}
      {integrations.map((i) => (
        <IntegrationResultCard key={`i-${i.id}`} integration={i} />
      ))}
    </ResultsStack>
  );

  const bloggersContent =
    bloggers.length > 0 ? (
      <ResultsStack>
        {bloggers.map((b) => (
          <BloggerResultCard key={b.id} blogger={b} />
        ))}
      </ResultsStack>
    ) : (
      <EmptyState title="Нет блогеров" description={`По запросу «${q}» блогеров не найдено.`} />
    );

  const integrationsContent =
    integrations.length > 0 ? (
      <ResultsStack>
        {integrations.map((i) => (
          <IntegrationResultCard key={i.id} integration={i} />
        ))}
      </ResultsStack>
    ) : (
      <EmptyState title="Нет интеграций" description={`По запросу «${q}» интеграций не найдено.`} />
    );

  return (
    <>
      <PageHeader title="Поиск" sub={sub} />
      <QueryStatusBoundary
        isLoading={isLoading}
        error={error}
        isEmpty={total === 0}
        emptyTitle="Ничего не нашлось"
        emptyDescription={`По запросу «${q}» нет ни блогеров, ни интеграций. Попробуйте другую формулировку.`}
      >
        <Tabs
          tabs={[
            { label: 'Все', count: total, content: allContent },
            { label: 'Блогеры', count: bloggers.length, content: bloggersContent },
            { label: 'Интеграции', count: integrations.length, content: integrationsContent },
          ]}
        />
      </QueryStatusBoundary>
    </>
  );
}

export default SearchPage;
