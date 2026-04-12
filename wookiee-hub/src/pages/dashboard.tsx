import { useState } from "react"
import { DashboardHeader } from "@/components/dashboard/dashboard-header"
import { DashboardMetrics } from "@/components/dashboard/dashboard-metrics"
import { OrdersChart } from "@/components/dashboard/orders-chart"
import { ExpensesTable } from "@/components/dashboard/expenses-table"
import { ModelTable } from "@/components/dashboard/model-table"
import { ModelDetailDrawer } from "@/components/dashboard/model-detail-drawer"
import { ActivityFeed } from "@/components/dashboard/activity-feed"
import { UpcomingShipments } from "@/components/dashboard/upcoming-shipments"
import { QuickStats } from "@/components/dashboard/quick-stats"
import { useApiQuery } from "@/hooks/use-api-query"
import { fetchFinanceByModel } from "@/lib/api/finance"
import { useFilterParams } from "@/stores/filters"

export function DashboardPage() {
  const params = useFilterParams()
  const [drawer, setDrawer] = useState<{ mp: string; model: string } | null>(null)

  const { data: modelRows } = useApiQuery(
    () => fetchFinanceByModel({ start_date: params.start_date, end_date: params.end_date, mp: params.mp }),
    [params.start_date, params.end_date, params.mp],
  )

  const handleRowClick = (mpKey: string, model: string) => {
    setDrawer({ mp: mpKey, model })
  }

  return (
    <div className="space-y-3">
      <DashboardHeader />
      <DashboardMetrics />
      <div className="grid grid-cols-1 lg:grid-cols-[1.3fr_1fr] gap-3">
        <OrdersChart />
        <ExpensesTable />
      </div>
      <ModelTable onRowClick={handleRowClick} />
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-[1fr_1fr_280px] gap-3">
        <ActivityFeed />
        <UpcomingShipments />
        <QuickStats />
      </div>

      <ModelDetailDrawer
        open={!!drawer}
        onClose={() => setDrawer(null)}
        mpKey={drawer?.mp ?? ""}
        modelName={drawer?.model ?? ""}
        rows={modelRows ?? []}
      />
    </div>
  )
}
