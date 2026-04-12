import { useEffect, useState } from "react"
import { matrixApi, type DbStatsResponse } from "@/lib/matrix-api"

export function DbStatsPage() {
  const [stats, setStats] = useState<DbStatsResponse | null>(null)
  const [health, setHealth] = useState<{ ok: boolean } | null>(null)

  useEffect(() => {
    matrixApi.getDbStats().then(setStats)
    matrixApi.getAdminHealth().then(setHealth)
  }, [])

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Статистика БД</h1>

      <div className="flex gap-4 mb-6">
        <div className="border rounded-lg p-4 min-w-[160px]">
          <p className="text-sm text-muted-foreground">Статус БД</p>
          <p className={`text-2xl font-bold ${health?.ok ? "text-green-600" : "text-red-600"}`}>
            {health?.ok ? "OK" : "Error"}
          </p>
        </div>
        <div className="border rounded-lg p-4 min-w-[160px]">
          <p className="text-sm text-muted-foreground">Всего записей</p>
          <p className="text-2xl font-bold">
            {stats?.total_records.toLocaleString("ru") ?? "—"}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {stats?.tables.map((t) => (
          <div key={t.name} className="border rounded-lg p-4">
            <p className="font-medium mb-1">{t.name}</p>
            <p className="text-2xl font-bold">{t.count.toLocaleString("ru")}</p>
            <div className="flex gap-3 mt-1 text-xs text-muted-foreground">
              <span className={t.growth_week > 0 ? "text-green-600" : ""}>
                +{t.growth_week} / нед
              </span>
              <span className={t.growth_month > 0 ? "text-green-600" : ""}>
                +{t.growth_month} / мес
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
