import { ChevronDown } from "lucide-react"
import { Popover, PopoverTrigger, PopoverContent } from "@/components/ui/popover"
import { Checkbox } from "@/components/ui/checkbox"
import { cn } from "@/lib/utils"

interface MultiSelectFilterProps {
  label: string
  options: { value: string; label: string }[]
  selected: string[]
  onChange: (selected: string[]) => void
  className?: string
}

export function MultiSelectFilter({
  label,
  options,
  selected,
  onChange,
  className,
}: MultiSelectFilterProps) {
  const isAllOrNone = selected.length === 0 || selected.length === options.length
  const triggerText = isAllOrNone ? label : `${label} (${selected.length})`

  function handleToggle(value: string, checked: boolean) {
    if (checked) {
      onChange([...selected, value])
    } else {
      onChange(selected.filter((v) => v !== value))
    }
  }

  function handleSelectAll() {
    onChange(options.map((o) => o.value))
  }

  function handleReset() {
    onChange([])
  }

  return (
    <Popover>
      <PopoverTrigger
        className={cn(
          "flex items-center gap-1.5 bg-bg-soft border border-border rounded-md px-3 py-1.5 text-[12px] text-muted-foreground hover:bg-bg-hover hover:text-foreground transition-colors",
          className
        )}
      >
        {triggerText}
        <ChevronDown className="size-3 opacity-50" />
      </PopoverTrigger>
      <PopoverContent align="start" className="w-56 p-2">
        <div className="flex items-center justify-between px-1 pb-1.5">
          <button
            type="button"
            className="text-[11px] text-accent hover:underline"
            onClick={handleSelectAll}
          >
            Выбрать все
          </button>
          <button
            type="button"
            className="text-[11px] text-accent hover:underline"
            onClick={handleReset}
          >
            Сбросить
          </button>
        </div>
        <div className="max-h-[200px] overflow-y-auto">
          {options.map((option) => (
            <label
              key={option.value}
              className="flex items-center gap-2 py-1.5 px-1 hover:bg-bg-hover rounded cursor-pointer"
            >
              <Checkbox
                checked={selected.includes(option.value)}
                onCheckedChange={(checked) =>
                  handleToggle(option.value, checked as boolean)
                }
              />
              <span className="text-[13px]">{option.label}</span>
            </label>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  )
}
