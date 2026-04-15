import { Star } from "lucide-react"
import { StatusPill } from "@/components/shared/status-pill"
import { formatNumber } from "@/lib/format"
import type { CatalogModel } from "@/types/catalog"

interface CatalogGridProps {
  models: CatalogModel[]
}

export function CatalogGrid({ models }: CatalogGridProps) {
  return (
    <div className="grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-3">
      {models.map((model) => (
        <div
          key={model.id}
          className="bg-card border border-border rounded-[10px] overflow-hidden hover:border-accent-border hover:shadow-glow transition-all duration-150 cursor-pointer"
        >
          <div className="h-[140px] bg-bg-hover flex items-center justify-center text-[40px]">
            {model.img}
          </div>

          <div className="px-3 py-2.5 space-y-1.5">
            <div className="flex items-center justify-between gap-2">
              <span className="text-[13px] font-semibold truncate">{model.name}</span>
              <StatusPill
                label={model.status === "active" ? "Активен" : "Черновик"}
                color={model.status === "active" ? "var(--wk-green)" : "var(--text-dim)"}
              />
            </div>

            <div className="text-[12px] text-muted-foreground">
              {model.category} &middot; {model.collection}
            </div>

            <div className="flex items-center justify-between">
              <span className="text-[13px] font-mono">{model.price}</span>
              <span className="text-[11px] text-text-dim">{model.skus} SKU</span>
            </div>

            <div className="flex items-center justify-between">
              {model.rating !== null ? (
                <span className="flex items-center gap-1 text-[12px]">
                  <Star size={12} className="text-yellow-500 fill-yellow-500" />
                  {model.rating}
                </span>
              ) : (
                <span className="text-[12px] text-muted-foreground">&mdash;</span>
              )}
              <span className="text-[12px] text-muted-foreground">
                {model.orders > 0 ? `${formatNumber(model.orders)} заказов` : "\u2014"}
              </span>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
