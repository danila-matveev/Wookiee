import { Clock } from 'lucide-react'
import { PageHeader } from '@/components/layout/page-header'
import { EmptyState } from '@/components/ui/empty-state'

export function HealthPage() {
  return (
    <div className="space-y-5">
      <PageHeader
        kicker="ОПЕРАЦИИ"
        title="Состояние системы"
        breadcrumbs={[
          { label: 'Операции', to: '/operations' },
          { label: 'Состояние системы', to: '/operations/health' },
        ]}
        description="Мониторинг сервисов, очередей и зависимостей"
      />
      <EmptyState
        icon={<Clock size={32} strokeWidth={1.5} aria-hidden />}
        title="Раздел в разработке"
        description="Будет доступен в следующей фазе: health-check агентов, статусы cron-задач, очереди"
        className="border border-dashed border-border rounded-xl"
      />
    </div>
  )
}
