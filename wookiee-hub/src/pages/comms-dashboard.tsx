import { useState, useMemo } from "react"
import { CommsDashboardHeader } from "@/components/comms/comms-dashboard-header"
import { CommsDashboardTabs } from "@/components/comms/comms-dashboard-tabs"
import { CommsDashboardMetrics } from "@/components/comms/comms-dashboard-metrics"
import { CommsDashboardChart } from "@/components/comms/comms-dashboard-chart"
import { CommsDashboardTopProducts } from "@/components/comms/comms-dashboard-top-products"
import { CommsDashboardStores } from "@/components/comms/comms-dashboard-stores"
import { useCommsStore } from "@/stores/comms"
import {
  commsResponseTimeData,
  commsStoreBreakdown,
} from "@/data/comms-mock"
import type { DateRange } from "react-day-picker"
import type { ReviewSource, CommsDashboardMetrics as MetricsType, TopProduct, StoreBreakdown } from "@/types/comms"

function defaultDateRange(): DateRange {
  const to = new Date()
  const from = new Date()
  from.setDate(from.getDate() - 14)
  return { from, to }
}

export function CommsDashboardPage() {
  const [selectedConnectionId, setSelectedConnectionId] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<ReviewSource | "all">("all")
  const [dateRange, setDateRange] = useState<DateRange | undefined>(defaultDateRange)
  const reviews = useCommsStore((s) => s.reviews)

  // Filter metrics/products/stores by connection when a specific store is selected
  const filteredData = useMemo(() => {
    const filtered = reviews.filter((r) => {
      if (selectedConnectionId && r.connectionId !== selectedConnectionId) return false
      if (activeTab !== "all" && r.source !== activeTab) return false
      if (dateRange?.from) {
        const reviewDate = new Date(r.createdAt)
        if (reviewDate < dateRange.from) return false
        if (dateRange.to) {
          const endOfDay = new Date(dateRange.to)
          endOfDay.setHours(23, 59, 59, 999)
          if (reviewDate > endOfDay) return false
        }
      }
      return true
    })

    const totalReceived = filtered.length
    const awaitingPublish = filtered.filter((r) => ["ai_generated", "approved"].includes(r.status)).length
    const unanswered = filtered.filter((r) => r.status === "new").length
    const rated = filtered.filter((r) => r.rating > 0)
    const avgRating = rated.length > 0 ? rated.reduce((s, r) => s + r.rating, 0) / rated.length : 0
    const positiveCount = rated.filter((r) => r.rating >= 4).length

    const metrics: MetricsType = {
      totalReceived,
      awaitingPublish,
      unanswered,
      unansweredPercent: totalReceived > 0 ? (unanswered / totalReceived) * 100 : 0,
      avgRating: Math.round(avgRating * 10) / 10,
      positivePercent: rated.length > 0 ? Math.round((positiveCount / rated.length) * 1000) / 10 : 0,
    }

    // Top products from filtered reviews
    const productMap = new Map<string, { name: string; article: string; total: number; sum: number }>()
    for (const r of filtered) {
      if (r.rating === 0) continue
      const existing = productMap.get(r.productArticle)
      if (existing) {
        existing.total++
        existing.sum += r.rating
      } else {
        productMap.set(r.productArticle, { name: r.productName, article: r.productArticle, total: 1, sum: r.rating })
      }
    }
    const topProducts: TopProduct[] = Array.from(productMap.values())
      .map((p) => ({ name: p.name, article: p.article, reviewCount: p.total, avgRating: Math.round((p.sum / p.total) * 10) / 10 }))
      .sort((a, b) => b.reviewCount - a.reviewCount)
      .slice(0, 6)

    // Store breakdown from filtered reviews
    const storeMap = new Map<string, { connectionName: string; serviceType: "wildberries" | "ozon"; total: number; sum: number }>()
    for (const r of filtered) {
      const existing = storeMap.get(r.connectionId)
      if (existing) {
        existing.total++
        if (r.rating > 0) existing.sum += r.rating
      } else {
        const breakdown = commsStoreBreakdown.find((s) => s.connectionId === r.connectionId)
        storeMap.set(r.connectionId, {
          connectionName: breakdown?.connectionName ?? r.connectionId,
          serviceType: r.serviceType,
          total: 1,
          sum: r.rating > 0 ? r.rating : 0,
        })
      }
    }
    const stores: StoreBreakdown[] = Array.from(storeMap.entries()).map(([id, s]) => ({
      connectionId: id,
      connectionName: s.connectionName,
      serviceType: s.serviceType,
      reviewCount: s.total,
      avgRating: s.total > 0 ? Math.round((s.sum / s.total) * 10) / 10 : 0,
    }))

    return { metrics, topProducts, stores }
  }, [reviews, selectedConnectionId, activeTab, dateRange])

  const periodLabel = useMemo(() => {
    if (!dateRange?.from || !dateRange?.to) return "за всё время"
    const days = Math.round((dateRange.to.getTime() - dateRange.from.getTime()) / (1000 * 60 * 60 * 24))
    if (days === 0) return "за сегодня"
    return `за ${days} ${days === 1 ? "день" : days < 5 ? "дня" : "дней"}`
  }, [dateRange])

  return (
    <div className="space-y-4">
      <CommsDashboardHeader
        selectedConnectionId={selectedConnectionId}
        onConnectionChange={setSelectedConnectionId}
        dateRange={dateRange}
        onDateRangeChange={setDateRange}
      />
      <CommsDashboardTabs activeTab={activeTab} onTabChange={setActiveTab} />
      <CommsDashboardMetrics metrics={filteredData.metrics} />
      <div className="grid grid-cols-1 lg:grid-cols-[1.3fr_1fr] gap-3">
        <CommsDashboardChart
          data={commsResponseTimeData.filter((point) => {
            if (!dateRange?.from) return true
            const [day, month] = point.date.split(".").map(Number)
            const pointDate = new Date(2026, month - 1, day)
            if (pointDate < dateRange.from) return false
            if (dateRange.to) {
              const endOfDay = new Date(dateRange.to)
              endOfDay.setHours(23, 59, 59, 999)
              if (pointDate > endOfDay) return false
            }
            return true
          })}
          periodLabel={periodLabel}
        />
        <CommsDashboardTopProducts products={filteredData.topProducts} />
      </div>
      <CommsDashboardStores stores={filteredData.stores} />
    </div>
  )
}
