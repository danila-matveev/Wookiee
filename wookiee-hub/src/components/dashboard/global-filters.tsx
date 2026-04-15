import { DateRangePicker } from "@/components/shared/date-range-picker"
import { useFiltersStore } from "@/stores/filters"
import { cn } from "@/lib/utils"
import type { DateRange } from "react-day-picker"

const mpOptions: { value: "wb" | "ozon" | "all"; label: string }[] = [
  { value: "all", label: "Все МП" },
  { value: "wb", label: "Wildberries" },
  { value: "ozon", label: "Ozon" },
]

export function GlobalFilters({ className }: { className?: string }) {
  const { dateRange, marketplace, setDateRange, setMarketplace } =
    useFiltersStore()

  const handleDateChange = (range: DateRange | undefined) => {
    if (range?.from && range?.to) {
      setDateRange({ from: range.from, to: range.to })
    }
  }

  return (
    <div className={cn("flex items-center gap-2 flex-wrap", className)}>
      <DateRangePicker
        value={{ from: dateRange.from, to: dateRange.to }}
        onChange={handleDateChange}
      />
      <div className="flex gap-1 bg-bg-soft border border-border rounded-md p-0.5">
        {mpOptions.map((opt) => (
          <button
            key={opt.value}
            type="button"
            onClick={() => setMarketplace(opt.value)}
            className={cn(
              "px-3 py-1 text-[12px] rounded-[5px] transition-colors",
              marketplace === opt.value
                ? "bg-accent text-accent-foreground font-semibold"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  )
}
