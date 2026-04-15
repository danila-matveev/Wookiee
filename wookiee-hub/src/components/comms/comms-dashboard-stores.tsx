import { Star } from "lucide-react"
import { cn } from "@/lib/utils"
import { getServiceDef } from "@/config/service-registry"
import type { StoreBreakdown } from "@/types/comms"

interface CommsDashboardStoresProps {
  stores: StoreBreakdown[]
  className?: string
}

export function CommsDashboardStores({ stores, className }: CommsDashboardStoresProps) {
  return (
    <div className={cn("bg-card border border-border rounded-[10px] p-4", className)}>
      <h3 className="text-sm font-semibold mb-3">Разбивка по магазинам</h3>
      <div className="space-y-3">
        {stores.map((store) => {
          const def = getServiceDef(store.serviceType)
          return (
            <div key={store.connectionId} className="flex items-center gap-3">
              <div
                className="w-8 h-8 rounded-lg flex items-center justify-center text-[11px] font-bold text-white shrink-0"
                style={{ backgroundColor: def.color }}
              >
                {def.label.slice(0, 2).toUpperCase()}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-[13px] font-medium truncate">{store.connectionName}</div>
                <div className="text-[11px] text-muted-foreground">{store.reviewCount} отзывов</div>
              </div>
              <div className="flex items-center gap-1 shrink-0">
                <Star size={12} className="text-amber-400 fill-amber-400" />
                <span className="text-[13px] font-semibold tabular-nums">{store.avgRating.toFixed(1)}</span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
