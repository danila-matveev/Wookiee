export function CalendarPage() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold text-foreground">Календарь публикаций</h1>
        <p className="text-sm text-muted-foreground mt-0.5">Загрузка...</p>
      </div>
      <div className="h-96 rounded-xl bg-muted animate-pulse" />
    </div>
  )
}
