import { useState } from "react"
import { SlidersHorizontal } from "lucide-react"
import { Popover, PopoverTrigger, PopoverContent } from "@/components/ui/popover"
import { Checkbox } from "@/components/ui/checkbox"
import { Button } from "@/components/ui/button"
import { DateRangePicker } from "@/components/shared/date-range-picker"
import { useCommsStore } from "@/stores/comms"
import { useIntegrationsStore } from "@/stores/integrations"
import { getServiceDef } from "@/config/service-registry"
import type { DateRange } from "react-day-picker"
import { useMemo } from "react"

const ratingOptions = [5, 4, 3, 2, 1] as const

export function ReviewsFilterPopover() {
  const { filters, setFilters } = useCommsStore()
  const allConnections = useIntegrationsStore((s) => s.connections)
  const connections = useMemo(() => allConnections.filter((c) => c.status === "active"), [allConnections])

  // Local draft state so user can "apply" or "reset"
  const [draftRatings, setDraftRatings] = useState<number[]>(filters.ratings)
  const [draftHasText, setDraftHasText] = useState<boolean | undefined>(filters.hasText)
  const [draftHasPhoto, setDraftHasPhoto] = useState<boolean | undefined>(filters.hasPhoto)
  const [draftConnectionIds, setDraftConnectionIds] = useState<string[]>(filters.connectionIds)
  const [draftDateRange, setDraftDateRange] = useState<DateRange | undefined>(
    filters.dateRange ? { from: filters.dateRange.from, to: filters.dateRange.to } : undefined
  )
  const [open, setOpen] = useState(false)

  // Sync draft from store when popover opens
  const handleOpenChange = (isOpen: boolean) => {
    if (isOpen) {
      setDraftRatings(filters.ratings)
      setDraftHasText(filters.hasText)
      setDraftHasPhoto(filters.hasPhoto)
      setDraftConnectionIds(filters.connectionIds)
      setDraftDateRange(
        filters.dateRange ? { from: filters.dateRange.from, to: filters.dateRange.to } : undefined
      )
    }
    setOpen(isOpen)
  }

  const toggleRating = (r: number) => {
    setDraftRatings((prev) => (prev.includes(r) ? prev.filter((v) => v !== r) : [...prev, r]))
  }

  const toggleConnection = (id: string) => {
    setDraftConnectionIds((prev) => (prev.includes(id) ? prev.filter((v) => v !== id) : [...prev, id]))
  }

  const handleApply = () => {
    setFilters({
      ratings: draftRatings,
      hasText: draftHasText,
      hasPhoto: draftHasPhoto,
      connectionIds: draftConnectionIds,
      dateRange:
        draftDateRange?.from && draftDateRange?.to
          ? { from: draftDateRange.from, to: draftDateRange.to }
          : undefined,
    })
    setOpen(false)
  }

  const handleReset = () => {
    setDraftRatings([])
    setDraftHasText(undefined)
    setDraftHasPhoto(undefined)
    setDraftConnectionIds([])
    setDraftDateRange(undefined)
  }

  const hasActiveFilters =
    filters.ratings.length > 0 ||
    filters.hasText !== undefined ||
    filters.hasPhoto !== undefined ||
    filters.connectionIds.length > 0 ||
    filters.dateRange !== undefined

  return (
    <Popover open={open} onOpenChange={handleOpenChange}>
      <PopoverTrigger
        className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-[13px] font-medium transition-colors ${
          hasActiveFilters
            ? "border-accent bg-accent-soft text-accent"
            : "border-border bg-card text-muted-foreground hover:text-foreground hover:bg-bg-hover"
        }`}
      >
        <SlidersHorizontal size={14} />
        Фильтры
        {hasActiveFilters && (
          <span className="ml-0.5 size-1.5 rounded-full bg-accent" />
        )}
      </PopoverTrigger>
      <PopoverContent align="start" className="w-80 p-0">
        <div className="max-h-[420px] overflow-y-auto p-3 space-y-4">
          {/* Date range */}
          <div className="space-y-1.5">
            <div className="text-[12px] font-medium text-muted-foreground uppercase tracking-wide">
              Период
            </div>
            <DateRangePicker value={draftDateRange} onChange={setDraftDateRange} />
          </div>

          {/* Ratings */}
          <div className="space-y-1.5">
            <div className="text-[12px] font-medium text-muted-foreground uppercase tracking-wide">
              Оценки
            </div>
            <div className="flex flex-col gap-1">
              {ratingOptions.map((r) => (
                <label
                  key={r}
                  className="flex items-center gap-2 cursor-pointer py-0.5"
                >
                  <Checkbox
                    checked={draftRatings.includes(r)}
                    onCheckedChange={() => toggleRating(r)}
                  />
                  <span className="text-[13px]">
                    {"★".repeat(r)}{"☆".repeat(5 - r)}
                  </span>
                </label>
              ))}
            </div>
          </div>

          {/* Has text */}
          <div className="space-y-1.5">
            <div className="text-[12px] font-medium text-muted-foreground uppercase tracking-wide">
              Текст
            </div>
            <div className="flex flex-col gap-1">
              <label className="flex items-center gap-2 cursor-pointer py-0.5">
                <Checkbox
                  checked={draftHasText === true}
                  onCheckedChange={() => setDraftHasText(draftHasText === true ? undefined : true)}
                />
                <span className="text-[13px]">С текстом</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer py-0.5">
                <Checkbox
                  checked={draftHasText === false}
                  onCheckedChange={() => setDraftHasText(draftHasText === false ? undefined : false)}
                />
                <span className="text-[13px]">Без текста</span>
              </label>
            </div>
          </div>

          {/* Has photo */}
          <div className="space-y-1.5">
            <div className="text-[12px] font-medium text-muted-foreground uppercase tracking-wide">
              Фото
            </div>
            <div className="flex flex-col gap-1">
              <label className="flex items-center gap-2 cursor-pointer py-0.5">
                <Checkbox
                  checked={draftHasPhoto === true}
                  onCheckedChange={() => setDraftHasPhoto(draftHasPhoto === true ? undefined : true)}
                />
                <span className="text-[13px]">С фото</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer py-0.5">
                <Checkbox
                  checked={draftHasPhoto === false}
                  onCheckedChange={() => setDraftHasPhoto(draftHasPhoto === false ? undefined : false)}
                />
                <span className="text-[13px]">Без фото</span>
              </label>
            </div>
          </div>

          {/* Connections / stores */}
          {connections.length > 0 && (
            <div className="space-y-1.5">
              <div className="text-[12px] font-medium text-muted-foreground uppercase tracking-wide">
                Магазины
              </div>
              <div className="flex flex-col gap-1">
                {connections.map((c) => {
                  const def = getServiceDef(c.serviceType)
                  return (
                    <label
                      key={c.id}
                      className="flex items-center gap-2 cursor-pointer py-0.5"
                    >
                      <Checkbox
                        checked={draftConnectionIds.includes(c.id)}
                        onCheckedChange={() => toggleConnection(c.id)}
                      />
                      <span className="text-[13px]">
                        {def.label} — {c.name}
                      </span>
                    </label>
                  )
                })}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between gap-2 border-t border-border p-2.5">
          <Button variant="ghost" size="sm" onClick={handleReset}>
            Сбросить
          </Button>
          <Button size="sm" onClick={handleApply}>
            Применить
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  )
}
