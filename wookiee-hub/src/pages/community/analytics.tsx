import { useState } from "react"
import { PageHeader } from "@/components/layout/page-header"
import { CommsAnalyticsHeader } from "@/components/community/analytics-header"
import { CommsAnalyticsMetrics } from "@/components/community/analytics-metrics"
import { AnalyticsResponseChart } from "@/components/community/analytics-response-chart"
import { AnalyticsRatingChart } from "@/components/community/analytics-rating-chart"
import { AnalyticsStoresTable } from "@/components/community/analytics-stores-table"
import { useDocumentTitle } from "@/hooks/use-document-title"

export function AnalyticsPage() {
  useDocumentTitle("Аналитика коммуникаций")
  const [period, setPeriod] = useState("28")
  const [selectedConnectionId, setSelectedConnectionId] = useState<string | null>(null)

  return (
    <div className="space-y-4">
      <PageHeader
        title="Аналитика коммуникаций"
      />
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
