import { create } from "zustand"
import { persist } from "zustand/middleware"
import { subDays, startOfDay, format } from "date-fns"

interface FiltersState {
  dateRange: { from: Date; to: Date }
  marketplace: "wb" | "ozon" | "all"
  setDateRange: (range: { from: Date; to: Date }) => void
  setMarketplace: (mp: "wb" | "ozon" | "all") => void
}

/** Helper: format Date to yyyy-MM-dd */
function fmtDate(d: Date): string {
  return format(d, "yyyy-MM-dd")
}

/** Selector — avoids recreating on every render */
export function useFilterParams() {
  const { dateRange, marketplace } = useFiltersStore()
  const startDate = fmtDate(dateRange.from)
  const endDate = fmtDate(dateRange.to)
  return { startDate, endDate, marketplace, start_date: startDate, end_date: endDate, mp: marketplace === "all" ? undefined : marketplace } as const
}

export const useFiltersStore = create<FiltersState>()(
  persist(
    (set) => ({
      dateRange: {
        from: startOfDay(subDays(new Date(), 7)),
        to: startOfDay(subDays(new Date(), 1)),
      },
      marketplace: "all",
      setDateRange: (range) => set({ dateRange: range }),
      setMarketplace: (marketplace) => set({ marketplace }),
    }),
    {
      name: "wookiee-filters",
      // Serialize/deserialize Date objects
      storage: {
        getItem: (name) => {
          const raw = localStorage.getItem(name)
          if (!raw) return null
          const parsed = JSON.parse(raw)
          if (parsed?.state?.dateRange) {
            parsed.state.dateRange.from = new Date(parsed.state.dateRange.from)
            parsed.state.dateRange.to = new Date(parsed.state.dateRange.to)
          }
          return parsed
        },
        setItem: (name, value) => localStorage.setItem(name, JSON.stringify(value)),
        removeItem: (name) => localStorage.removeItem(name),
      },
    },
  ),
)
