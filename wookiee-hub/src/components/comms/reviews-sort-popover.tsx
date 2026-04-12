import { ArrowUpDown } from "lucide-react"
import { Popover, PopoverTrigger, PopoverContent } from "@/components/ui/popover"
import { useCommsStore } from "@/stores/comms"
import { cn } from "@/lib/utils"
import type { ReviewFilters } from "@/types/comms"

const sortOptions: { value: ReviewFilters["sortBy"]; label: string }[] = [
  { value: "newest", label: "Сначала новые" },
  { value: "oldest", label: "Сначала старые" },
  { value: "rating_desc", label: "По убыванию оценок" },
  { value: "rating_asc", label: "По возрастанию оценок" },
]

export function ReviewsSortPopover() {
  const { filters, setFilters } = useCommsStore()

  return (
    <Popover>
      <PopoverTrigger
        className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-border bg-card text-[13px] font-medium text-muted-foreground hover:text-foreground hover:bg-bg-hover transition-colors"
      >
        <ArrowUpDown size={14} />
        Сортировка
      </PopoverTrigger>
      <PopoverContent align="start" className="w-56 p-1.5">
        {sortOptions.map((opt) => (
          <button
            key={opt.value}
            onClick={() => setFilters({ sortBy: opt.value })}
            className={cn(
              "w-full text-left px-2.5 py-1.5 rounded-md text-[13px] transition-colors",
              filters.sortBy === opt.value
                ? "bg-accent-soft text-accent font-medium"
                : "text-foreground hover:bg-bg-hover"
            )}
          >
            {opt.label}
          </button>
        ))}
      </PopoverContent>
    </Popover>
  )
}
