import { useState } from "react"
import { Filter } from "lucide-react"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { Checkbox } from "@/components/ui/checkbox"
import { Button } from "@/components/ui/button"
import { useMatrixStore, type FilterEntry } from "@/stores/matrix-store"

export interface FilterableDef {
  field: string
  label: string
  lookupTable?: string
}

interface FilterPopoverProps {
  filterableDefs: FilterableDef[]
  onAddFilter: (entry: FilterEntry) => void
}

export function FilterPopover({ filterableDefs, onAddFilter }: FilterPopoverProps) {
  const [open, setOpen] = useState(false)
  const [step, setStep] = useState<"field" | "value">("field")
  const [selectedDef, setSelectedDef] = useState<FilterableDef | null>(null)
  const [selectedIds, setSelectedIds] = useState<number[]>([])

  const lookupCache = useMatrixStore((s) => s.lookupCache)

  // Only show fields that have a lookupTable
  const filterableFields = filterableDefs.filter((d) => d.lookupTable)

  function handleOpenChange(nextOpen: boolean) {
    setOpen(nextOpen)
    if (!nextOpen) {
      // Reset state when closing
      setStep("field")
      setSelectedDef(null)
      setSelectedIds([])
    }
  }

  function handleFieldSelect(def: FilterableDef) {
    setSelectedDef(def)
    setSelectedIds([])
    setStep("value")
  }

  function handleToggleId(id: number) {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    )
  }

  function handleApply() {
    if (!selectedDef || selectedIds.length === 0) return
    const items = lookupCache[selectedDef.lookupTable!] ?? []
    const valueLabels = selectedIds
      .map((id) => items.find((item) => item.id === id)?.nazvanie ?? String(id))
    onAddFilter({
      field: selectedDef.field,
      label: selectedDef.label,
      values: selectedIds,
      valueLabels,
    })
    handleOpenChange(false)
  }

  const lookupItems = selectedDef?.lookupTable
    ? (lookupCache[selectedDef.lookupTable] ?? [])
    : []

  return (
    <Popover open={open} onOpenChange={handleOpenChange}>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
        >
          <Filter className="h-3.5 w-3.5" />
          <span className="text-xs">+Фильтр</span>
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-52 p-2">
        {step === "field" && (
          <>
            <p className="mb-2 px-1 text-xs font-medium text-muted-foreground">
              Выберите поле
            </p>
            <div className="space-y-0.5">
              {filterableFields.map((def) => (
                <button
                  key={def.field}
                  type="button"
                  onClick={() => handleFieldSelect(def)}
                  className="w-full rounded px-2 py-1.5 text-left text-xs hover:bg-accent/50 focus:outline-none"
                >
                  {def.label}
                </button>
              ))}
              {filterableFields.length === 0 && (
                <p className="px-1 py-1 text-xs text-muted-foreground">
                  Нет доступных фильтров
                </p>
              )}
            </div>
          </>
        )}

        {step === "value" && selectedDef && (
          <>
            <div className="mb-2 flex items-center gap-1">
              <button
                type="button"
                onClick={() => { setStep("field"); setSelectedIds([]) }}
                className="text-xs text-muted-foreground hover:text-foreground"
              >
                ←
              </button>
              <p className="text-xs font-medium">{selectedDef.label}</p>
            </div>
            <div className="max-h-56 space-y-1 overflow-y-auto">
              {lookupItems.map((item) => (
                <label
                  key={item.id}
                  className="flex cursor-pointer items-center gap-2 rounded px-1 py-0.5 hover:bg-accent/30"
                >
                  <Checkbox
                    checked={selectedIds.includes(item.id)}
                    onCheckedChange={() => handleToggleId(item.id)}
                  />
                  <span className="text-xs">{item.nazvanie}</span>
                </label>
              ))}
              {lookupItems.length === 0 && (
                <p className="px-1 py-1 text-xs text-muted-foreground">
                  Нет значений
                </p>
              )}
            </div>
            <div className="mt-2 flex justify-end">
              <Button
                size="sm"
                className="h-7 text-xs"
                disabled={selectedIds.length === 0}
                onClick={handleApply}
              >
                Применить
              </Button>
            </div>
          </>
        )}
      </PopoverContent>
    </Popover>
  )
}
