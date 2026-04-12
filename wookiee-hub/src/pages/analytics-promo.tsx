import { useState } from "react"
import { cn } from "@/lib/utils"
import { GlobalFilters } from "@/components/dashboard/global-filters"
import { PromoHeader } from "@/components/promo/promo-header"
import { PromoChart } from "@/components/promo/promo-chart"
import { PromoFunnelTab } from "@/components/promo/promo-funnel-tab"
import { PromoByDatesTab } from "@/components/promo/promo-by-dates-tab"
import { PromoModelTable } from "@/components/promo/promo-model-table"
import { PromoExternalTab } from "@/components/promo/promo-external-tab"

const tabs = [
  { id: "funnel", label: "Аудит воронок" },
  { id: "dates", label: "По датам" },
  { id: "campaigns", label: "По РК" },
  { id: "traffic", label: "Общий трафик" },
  { id: "external", label: "Внешн. трафик" },
] as const

type TabId = (typeof tabs)[number]["id"]

function TabContent({ tab }: { tab: TabId }) {
  switch (tab) {
    case "funnel":
      return <PromoFunnelTab />
    case "dates":
      return <PromoByDatesTab />
    case "campaigns":
      return <PromoModelTable />
    case "traffic":
      return <PromoModelTable />
    case "external":
      return <PromoExternalTab />
    default:
      return null
  }
}

export function AnalyticsPromoPage() {
  const [activeTab, setActiveTab] = useState<TabId>("funnel")

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold">Продвижение</h1>
        <GlobalFilters />
      </div>

      <PromoHeader />
      <PromoChart />

      <div className="bg-card border border-border rounded-[10px] p-4">
        <div className="flex gap-4 border-b border-border mb-4">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                "pb-2 text-[13px] font-medium transition-colors",
                tab.id === activeTab
                  ? "text-foreground border-b-2 border-accent"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <TabContent tab={activeTab} />
      </div>
    </div>
  )
}
