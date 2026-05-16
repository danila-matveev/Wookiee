import { useState, useEffect } from "react"
import { useSearchParams } from "react-router-dom"
import { fetchRnpWeeks } from "@/api/rnp"
import type { RnpWeek } from "@/types/rnp"
import { PageHeader } from "@/components/layout/page-header"
import { RnpHelpBlock } from "@/components/analytics/rnp-help-block"
import { RnpFilters } from "@/components/analytics/rnp-filters"
import { RnpSummaryCards } from "@/components/analytics/rnp-summary-cards"
import { TabOrders } from "@/components/analytics/rnp-tabs/tab-orders"
import { TabFunnel } from "@/components/analytics/rnp-tabs/tab-funnel"
import { TabAdsTotal } from "@/components/analytics/rnp-tabs/tab-ads-total"
import { TabAdsInternal } from "@/components/analytics/rnp-tabs/tab-ads-internal"
import { TabAdsExternal } from "@/components/analytics/rnp-tabs/tab-ads-external"
import { TabMargin } from "@/components/analytics/rnp-tabs/tab-margin"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

const TABS = [
  { id: "orders",       label: "Заказы & Продажи" },
  { id: "funnel",       label: "Воронка" },
  { id: "ads-total",    label: "Реклама итого" },
  { id: "ads-internal", label: "Внутренняя" },
  { id: "ads-external", label: "Внешняя" },
  { id: "margin",       label: "Маржа & Прогноз" },
]

export function RnpPage() {
  const [searchParams] = useSearchParams()
  const [weeks, setWeeks] = useState<RnpWeek[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [extAdsAvailable, setExtAdsAvailable] = useState(true)

  async function load(params: { model: string; dateFrom: string; dateTo: string }) {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchRnpWeeks(params)
      setWeeks(data.weeks)
      setExtAdsAvailable(data.ext_ads_available)
    } catch {
      setError("Ошибка загрузки данных. Проверьте подключение к API.")
    } finally {
      setLoading(false)
    }
  }

  // Auto-load if URL params already have model+dates (e.g. bookmarked URL)
  useEffect(() => {
    const model = searchParams.get("model")
    const from  = searchParams.get("from")
    const to    = searchParams.get("to")
    if (model && from && to) {
      load({ model, dateFrom: from, dateTo: to })
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="space-y-4">
      <PageHeader
        kicker="АНАЛИТИКА"
        title="РНП — Рука на пульсе"
        breadcrumbs={[
          { label: "Аналитика", to: "/analytics" },
          { label: "Рука на пульсе", to: "/analytics/rnp" },
        ]}
        description="Недельная динамика по модели: заказы, воронка, реклама, маржа и прогноз."
      />

      <RnpHelpBlock />

      <RnpFilters onApply={load} loading={loading} />

      {error && (
        <div className="rounded-md bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {!extAdsAvailable && weeks.length > 0 && (
        <div className="rounded-md bg-amber-50 border border-amber-200 px-4 py-2 text-sm text-amber-700">
          Google Sheets недоступен — показаны только данные WB. Реклама из Sheets не отображается.
        </div>
      )}

      {weeks.length > 0 && (
        <>
          <RnpSummaryCards weeks={weeks} />

          <Tabs defaultValue="orders">
            <TabsList>
              {TABS.map(t => (
                <TabsTrigger key={t.id} value={t.id}>{t.label}</TabsTrigger>
              ))}
            </TabsList>
            <TabsContent value="orders">      <TabOrders weeks={weeks} /></TabsContent>
            <TabsContent value="funnel">      <TabFunnel weeks={weeks} /></TabsContent>
            <TabsContent value="ads-total">   <TabAdsTotal weeks={weeks} /></TabsContent>
            <TabsContent value="ads-internal"><TabAdsInternal weeks={weeks} /></TabsContent>
            <TabsContent value="ads-external"><TabAdsExternal weeks={weeks} /></TabsContent>
            <TabsContent value="margin">      <TabMargin weeks={weeks} /></TabsContent>
          </Tabs>
        </>
      )}

      {!loading && weeks.length === 0 && !error && (
        <div className="py-12 text-center text-muted-foreground text-sm">
          Выберите модель и период, нажмите «Обновить»
        </div>
      )}
    </div>
  )
}
