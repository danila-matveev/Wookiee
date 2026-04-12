import { useState } from "react"
import { Star } from "lucide-react"
import { cn } from "@/lib/utils"
import type { TopProduct } from "@/types/comms"

interface CommsDashboardTopProductsProps {
  products: TopProduct[]
  className?: string
}

export function CommsDashboardTopProducts({ products, className }: CommsDashboardTopProductsProps) {
  const [showPositive, setShowPositive] = useState(true)

  const sorted = [...products].sort((a, b) =>
    showPositive ? b.avgRating - a.avgRating : a.avgRating - b.avgRating
  )

  return (
    <div className={cn("bg-card border border-border rounded-[10px] p-4", className)}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold">Топ товаров</h3>
        <div className="flex gap-1 p-0.5 rounded-md bg-bg-soft">
          <button
            onClick={() => setShowPositive(true)}
            className={cn(
              "px-2 py-1 rounded text-[11px] font-medium transition-all",
              showPositive ? "bg-card text-foreground shadow-sm" : "text-muted-foreground"
            )}
          >
            Лучшие
          </button>
          <button
            onClick={() => setShowPositive(false)}
            className={cn(
              "px-2 py-1 rounded text-[11px] font-medium transition-all",
              !showPositive ? "bg-card text-foreground shadow-sm" : "text-muted-foreground"
            )}
          >
            Худшие
          </button>
        </div>
      </div>
      <div className="space-y-2">
        {sorted.map((product) => (
          <div key={product.article} className="flex items-center justify-between py-1.5">
            <div className="min-w-0 flex-1">
              <div className="text-[13px] font-medium truncate">{product.name}</div>
              <div className="text-[11px] text-muted-foreground">
                {product.internalArticle && <span>{product.internalArticle}</span>}
                {product.wbArticle && <span> · WB {product.wbArticle}</span>}
                {!product.wbArticle && <span> · {product.article}</span>}
                <span> · {product.reviewCount} отз.</span>
              </div>
            </div>
            <div className="flex items-center gap-1 ml-3 shrink-0">
              <Star size={12} className="text-amber-400 fill-amber-400" />
              <span className="text-[13px] font-semibold tabular-nums">{product.avgRating.toFixed(1)}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
