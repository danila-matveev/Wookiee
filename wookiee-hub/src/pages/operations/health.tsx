import { Clock } from 'lucide-react'
import { PageHeader } from '@/components/layout/page-header'
import { EmptyState } from '@/components/ui/empty-state'
import { useDocumentTitle } from '@/hooks/use-document-title'

export function HealthPage() {
  useDocumentTitle('Состояние системы')
  return (
    <div className="space-y-5">
      <PageHeader
        title="Состояние системы"
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
