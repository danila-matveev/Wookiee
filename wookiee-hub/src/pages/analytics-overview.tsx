import { useState } from "react"
import { GlobalFilters } from "@/components/dashboard/global-filters"
import { AnalyticsMetrics } from "@/components/analytics/analytics-metrics"
import { AnalyticsChart } from "@/components/analytics/analytics-chart"

export function AnalyticsOverviewPage() {
  const [activeTab, setActiveTab] = useState("revenue")

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold">Аналитика — Сводка</h1>
        <GlobalFilters />
      </div>
      <AnalyticsMetrics />
      <AnalyticsChart activeTab={activeTab} onTabChange={setActiveTab} />
    </div>
  )
}
