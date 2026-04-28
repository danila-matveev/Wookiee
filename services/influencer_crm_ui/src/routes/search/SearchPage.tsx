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
import { Skeleton } from '@/ui/Skeleton';
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
  lead: 'secondary',
  negotiation: 'info',
  agreed: 'info',
  content_received: 'info',
  content_approved: 'info',
  scheduled: 'warning',
  published: 'orange',
  paid: 'success',
  done: 'success',
  rejected: 'danger',
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
      to="/bloggers"
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
  // T18 punts on opening the IntegrationEditDrawer from search — re-mounting the
  // drawer on this page would mean threading queryClient state for substitutes/posts,
  // which is messy. We navigate to /integrations and let the user find the card on
  // the Kanban board. (See plan §"T18 — Global search".)
  const handleLabel = `Блогер #${integration.blogger_id}`;
  return (
    <Link
      to="/integrations"
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
  const { data, isLoading } = useSearch(q);

  const bloggers = data?.bloggers ?? [];
  const integrations = data?.integrations ?? [];
  const total = bloggers.length + integrations.length;

  const sub = q
    ? `по запросу «${q}»`
    : 'Введите запрос в поиске наверху, чтобы найти блогеров и интеграции.';

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

  if (isLoading) {
    return (
      <>
        <PageHeader title="Поиск" sub={sub} />
        <Skeleton className="h-64" />
      </>
    );
  }

  if (total === 0) {
    return (
      <>
        <PageHeader title="Поиск" sub={sub} />
        <EmptyState
          title="Ничего не нашлось"
          description={`По запросу «${q}» нет ни блогеров, ни интеграций. Попробуйте другую формулировку.`}
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
      <Tabs
        tabs={[
          { label: 'Все', count: total, content: allContent },
          { label: 'Блогеры', count: bloggers.length, content: bloggersContent },
          { label: 'Интеграции', count: integrations.length, content: integrationsContent },
        ]}
      />
    </>
  );
}

export default SearchPage;
