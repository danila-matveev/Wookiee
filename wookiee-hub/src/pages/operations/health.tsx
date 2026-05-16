import { PageHeader } from '@/components/layout/page-header'

export function HealthPage() {
  return (
    <div className="space-y-5">
      <PageHeader
        kicker="Operations"
        title="Состояние системы"
        breadcrumbs={[
          { label: 'Operations', to: '/operations' },
          { label: 'Health', to: '/operations/health' },
        ]}
        description="Мониторинг сервисов, очередей и зависимостей"
      />
      <div className="border border-dashed border-border rounded-xl p-12 text-center">
        <p className="text-[13px] font-medium text-foreground">Раздел в разработке</p>
        <p className="text-[12px] text-muted-foreground mt-1">
          Будет доступен в следующей фазе: health-check агентов, статусы cron-задач, очереди
        </p>
      </div>
    </div>
  )
}
