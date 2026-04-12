import { useState } from "react"
import { CommsAnalyticsHeader } from "@/components/comms/analytics-header"
import { CommsAnalyticsMetrics } from "@/components/comms/analytics-metrics"
import { AnalyticsResponseChart } from "@/components/comms/analytics-response-chart"
import { AnalyticsRatingChart } from "@/components/comms/analytics-rating-chart"
import { AnalyticsStoresTable } from "@/components/comms/analytics-stores-table"

export function CommsAnalyticsPage() {
  const [period, setPeriod] = useState("28")
  const [selectedConnectionId, setSelectedConnectionId] = useState<string | null>(null)

  return (
    <div className="space-y-4">
      <CommsAnalyticsHeader
        activePeriod={period}
        onPeriodChange={setPeriod}
        selectedConnectionId={selectedConnectionId}
        onConnectionChange={setSelectedConnectionId}
      />
      <CommsAnalyticsMetrics />
      <div className="grid grid-cols-1 lg:grid-cols-[1.3fr_1fr] gap-4">
        <AnalyticsResponseChart />
        <AnalyticsRatingChart />
      </div>
      <AnalyticsStoresTable />
    </div>
  )
}
