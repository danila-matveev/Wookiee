export function IntegrationsKanbanPage() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold text-foreground">Интеграции</h1>
        <p className="text-sm text-muted-foreground mt-0.5">Загрузка...</p>
      </div>
      <div className="h-64 rounded-xl bg-muted animate-pulse" />
    </div>
  )
}
