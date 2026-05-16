import { ChevronLeft, ChevronRight } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useIntegrations } from '@/hooks/crm/use-integrations';
import { PageHeader } from '@/components/layout/page-header';
import { IntegrationEditDrawer } from '@/pages/influence/integrations/IntegrationEditDrawer';
import { Button } from '@/components/crm/ui/Button';
import { FilterPill } from '@/components/crm/ui/FilterPill';
import { QueryStatusBoundary } from '@/components/crm/ui/QueryStatusBoundary';
import { Skeleton } from '@/components/crm/ui/Skeleton';
import { CalendarMonthGrid, toIsoDate } from './CalendarMonthGrid';

function formatMonthLabel(date: Date): string {
  const raw = new Intl.DateTimeFormat('ru-RU', { month: 'long', year: 'numeric' }).format(date);
  return raw.charAt(0).toUpperCase() + raw.slice(1);
}

export function CalendarPage() {
  const [monthDate, setMonthDate] = useState<Date>(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });

  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerIntegrationId, setDrawerIntegrationId] = useState<number | undefined>();
  const [drawerInitialDate, setDrawerInitialDate] = useState<string | undefined>();

  const { dateFrom, dateTo } = useMemo(() => {
    const start = new Date(monthDate.getFullYear(), monthDate.getMonth(), 1);
    const end = new Date(monthDate.getFullYear(), monthDate.getMonth() + 1, 0);
    return { dateFrom: toIsoDate(start), dateTo: toIsoDate(end) };
  }, [monthDate]);

  const { data, isLoading, error } = useIntegrations({
    date_from: dateFrom,
    date_to: dateTo,
    limit: 1000,
  });
  const integrations = data?.items ?? [];

  function goToPrevMonth() {
    setMonthDate((d) => new Date(d.getFullYear(), d.getMonth() - 1, 1));
  }
  function goToNextMonth() {
    setMonthDate((d) => new Date(d.getFullYear(), d.getMonth() + 1, 1));
  }
  function goToToday() {
    const now = new Date();
    setMonthDate(new Date(now.getFullYear(), now.getMonth(), 1));
  }

  function openEditDrawer(id: number) {
    setDrawerIntegrationId(id);
    setDrawerInitialDate(undefined);
    setDrawerOpen(true);
  }
  function openCreateDrawer(isoDate: string) {
    setDrawerIntegrationId(undefined);
    setDrawerInitialDate(isoDate);
    setDrawerOpen(true);
  }
  function closeDrawer() {
    setDrawerOpen(false);
  }

  return (
    <>
      <PageHeader
        kicker="ИНФЛЮЕНС"
        title="Календарь публикаций"
        breadcrumbs={[
          { label: 'Инфлюенс', to: '/influence/bloggers' },
          { label: 'Календарь', to: '/influence/calendar' },
        ]}
        description="Все интеграции по датам публикации. Клик по событию — редактирование. Клик по пустому дню — новая интеграция."
      />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium text-muted-fg">Вид</span>
        <FilterPill solid>Месяц</FilterPill>
        <FilterPill disabled className="opacity-60">
          Неделя <span className="ml-1 rounded-full bg-muted px-1.5 text-[10px]">soon</span>
        </FilterPill>
        <FilterPill disabled className="opacity-60">
          Список <span className="ml-1 rounded-full bg-muted px-1.5 text-[10px]">soon</span>
        </FilterPill>
      </div>

      <div className="mb-4 flex items-center gap-2">
        <Button variant="ghost" onClick={goToPrevMonth} aria-label="Предыдущий месяц">
          <ChevronLeft size={16} />
        </Button>
        <div className="font-display text-lg font-semibold text-fg">
          {formatMonthLabel(monthDate)}
        </div>
        <Button variant="ghost" onClick={goToNextMonth} aria-label="Следующий месяц">
          <ChevronRight size={16} />
        </Button>
        <Button variant="secondary" onClick={goToToday} className="ml-auto">
          Сегодня
        </Button>
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-4 text-xs text-muted-fg">
        <span className="inline-flex items-center gap-1.5">
          <span className="size-2 rounded-full bg-success" /> Опубликовано / оплачено
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="size-2 rounded-full bg-warning" /> Контент / запланировано
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="size-2 rounded-full bg-primary" /> Переговоры
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="size-2 rounded-full bg-muted-fg" /> Лид / отказ
        </span>
      </div>

      <QueryStatusBoundary
        isLoading={isLoading}
        error={error}
        loadingFallback={<Skeleton className="h-[600px]" />}
      >
        <CalendarMonthGrid
          monthDate={monthDate}
          integrations={integrations}
          onEventClick={openEditDrawer}
          onCellClick={openCreateDrawer}
        />
      </QueryStatusBoundary>

      <IntegrationEditDrawer
        open={drawerOpen}
        id={drawerIntegrationId}
        initialDate={drawerInitialDate}
        onClose={closeDrawer}
      />
    </>
  );
}

export default CalendarPage;
