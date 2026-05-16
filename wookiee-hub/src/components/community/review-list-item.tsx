import { Star } from "lucide-react"
import { cn } from "@/lib/utils"
import { getServiceDef } from "@/config/service-registry"
import type { Review } from "@/types/community"

interface ReviewListItemProps {
  review: Review
  isSelected: boolean
  onClick: () => void
}

export function ReviewListItem({ review, isSelected, onClick }: ReviewListItemProps) {
  const def = getServiceDef(review.serviceType)
  const dateStr = new Date(review.createdAt).toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit" })
  const preview = (review.comment || "").slice(0, 80) + ((review.comment || "").length > 80 ? "..." : "")

  return (
    <button
      onClick={onClick}
      className={cn(
        "w-full text-left p-3 rounded-lg border transition-all",
        isSelected
          ? "bg-accent-soft border-accent-border"
          : "bg-card border-border hover:border-accent-border/50"
      )}
    >
      <div className="flex items-center gap-2 mb-1.5">
        <span
          className="w-5 h-5 rounded flex items-center justify-center text-[9px] font-bold text-white shrink-0"
          style={{ backgroundColor: def.color }}
        >
          {def.label.slice(0, 2).toUpperCase()}
        </span>
        <span className="text-[11px] text-muted-foreground">{dateStr}</span>
        {review.source === "question" && (
          <span className="text-[10px] bg-blue-500/10 text-blue-600 px-1.5 py-0.5 rounded-full font-medium">Вопрос</span>
        )}
        <div className="flex-1" />
        {review.rating > 0 && (
          <div className="flex items-center gap-0.5">
            <Star size={10} className="text-amber-400 fill-amber-400" />
            <span className="text-[11px] font-medium tabular-nums">{review.rating}</span>
          </div>
        )}
      </div>
      <div className="text-[13px] font-medium truncate mb-0.5">{review.productName}</div>
      <div className="text-[12px] text-muted-foreground line-clamp-2 leading-relaxed">{preview}</div>
    </button>
  )
}
