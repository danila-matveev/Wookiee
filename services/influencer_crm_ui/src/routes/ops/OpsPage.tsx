import { formatDate, formatInt } from '@/lib/format';
import { useOpsHealth } from '@/hooks/use-ops';
import { PageHeader } from '@/layout/PageHeader';
import { Badge } from '@/ui/Badge';
import { KpiCard } from '@/ui/KpiCard';
import { QueryStatusBoundary } from '@/ui/QueryStatusBoundary';

// Human-readable age — keeps KpiCard value short ("3 мин") instead of dumping
// raw seconds. Threshold matches the cron cadence (MV refresh every 5 min).
function formatAge(seconds: number | null): string {
  if (seconds == null) return '—';
  if (seconds < 60) return `${seconds} с`;
  if (seconds < 3600) return `${Math.round(seconds / 60)} мин`;
  return `${Math.round(seconds / 3600)} ч`;
}

// Pick a tone for "ETL — последний запуск" KPI based on the run status.
function etlAccent(status: string | null): 'primary' | 'success' | 'pink' {
  if (status === 'success') return 'success';
  if (status === 'failed') return 'pink';
  return 'primary';
}

// Pick a tone for "Сбои за 24ч" KPI — pink when there's any failure
// or any stuck running ETL (>1h).
function failuresAccent(failed: number, staleRunning: number): 'success' | 'pink' {
  return failed > 0 || staleRunning > 0 ? 'pink' : 'success';
}

// Pick a tone for "Свежесть MV" — pink when older than the cron cadence (5 min)
// by a 2x safety margin.
function mvAccent(seconds: number | null): 'success' | 'pink' | 'primary' {
  if (seconds == null) return 'primary';
  return seconds > 600 ? 'pink' : 'success';
}

export function OpsPage() {
  const { data, isLoading, error } = useOpsHealth();

  return (
    <>
      <PageHeader title="Ops" sub="Состояние синхронизаций и расписаний CRM." />

      <QueryStatusBoundary isLoading={isLoading} error={error} isEmpty={!data}>
        {data && (
          <div className="space-y-5">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              <KpiCard
                title="ETL — последний запуск"
                accent={etlAccent(data.etl_last_run.status)}
                value={
                  data.etl_last_run.started_at
                    ? formatDate(data.etl_last_run.started_at)
                    : '—'
                }
                hint={data.etl_last_run.status ?? 'нет данных'}
              />
              <KpiCard
                title="Свежесть MV"
                accent={mvAccent(data.mv_age_seconds)}
                value={formatAge(data.mv_age_seconds)}
                hint="v_blogger_totals"
              />
              <KpiCard
                title="Сбои за 24ч"
                accent={failuresAccent(
                  data.etl_last_24h.failed,
                  data.etl_last_24h.stale_running,
                )}
                value={formatInt(data.etl_last_24h.failed)}
                hint={
                  data.etl_last_24h.stale_running > 0
                    ? `зависших: ${formatInt(data.etl_last_24h.stale_running)} · успешно: ${formatInt(data.etl_last_24h.success)}`
                    : `успешно: ${formatInt(data.etl_last_24h.success)}`
                }
              />
            </div>

            <section className="rounded-lg border border-border-strong bg-card p-4 shadow-warm">
              <h2 className="mb-3 text-sm font-semibold text-fg">Cron-задачи</h2>
              {data.cron_jobs.length === 0 ? (
                <p className="text-sm text-muted-fg">
                  Расписания не зарегистрированы. Примените миграции 010/011.
                </p>
              ) : (
                <table className="w-full text-sm">
                  <caption className="sr-only">Список запланированных cron-задач CRM</caption>
                  <thead className="text-[11px] uppercase tracking-wider text-muted-fg">
                    <tr>
                      <th scope="col" className="py-1 text-left font-semibold">
                        Задача
                      </th>
                      <th scope="col" className="py-1 text-left font-semibold">
                        Расписание
                      </th>
                      <th scope="col" className="py-1 text-left font-semibold">
                        Статус
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.cron_jobs.map((j) => (
                      <tr key={j.jobname} className="border-t border-border">
                        <td className="py-2 font-mono text-fg">{j.jobname}</td>
                        <td className="py-2 font-mono text-muted-fg">{j.schedule}</td>
                        <td className="py-2">
                          <Badge tone={j.active ? 'success' : 'secondary'}>
                            {j.active ? 'активна' : 'выключена'}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </section>

            <section className="rounded-lg border border-border-strong bg-card p-4 shadow-warm">
              <h2 className="mb-2 text-sm font-semibold text-fg">Очередь retention</h2>
              <dl className="grid grid-cols-1 gap-4 text-sm sm:grid-cols-2">
                <div>
                  <dt className="text-[11px] uppercase tracking-wider text-muted-fg">
                    audit_log &gt; 90 дн.
                  </dt>
                  <dd className="font-mono text-base text-fg">
                    {formatInt(data.retention.audit_log_eligible_for_delete)}
                  </dd>
                </div>
                <div>
                  <dt className="text-[11px] uppercase tracking-wider text-muted-fg">
                    snapshots &gt; 365 дн.
                  </dt>
                  <dd className="font-mono text-base text-fg">
                    {formatInt(data.retention.snapshots_eligible_for_delete)}
                  </dd>
                </div>
              </dl>
            </section>
          </div>
        )}
      </QueryStatusBoundary>
    </>
  );
}

export default OpsPage;
