export function HealthPage() {
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold text-foreground">Состояние системы</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Мониторинг сервисов, очередей и зависимостей
        </p>
      </div>
      <div className="border border-dashed border-border rounded-xl p-12 text-center">
        <p className="text-[13px] font-medium text-foreground">Раздел в разработке</p>
        <p className="text-[12px] text-muted-foreground mt-1">
          Будет доступен в следующей фазе: health-check агентов, статусы cron-задач, очереди
        </p>
      </div>
    </div>
  )
}
