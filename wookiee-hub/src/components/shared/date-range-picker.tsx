import { CalendarDays } from "lucide-react"
import { Popover, PopoverTrigger, PopoverContent } from "@/components/ui/popover"
import { Calendar } from "@/components/ui/calendar"
import { cn } from "@/lib/utils"
import type { DateRange } from "react-day-picker"
import { ru } from "date-fns/locale"

/** Yesterday — latest day with complete data */
function yesterday(): Date {
  const d = new Date()
  d.setDate(d.getDate() - 1)
  d.setHours(0, 0, 0, 0)
  return d
}

const presets = [
  {
    label: "Вчера",
    getDates: (): DateRange => {
      const d = yesterday()
      return { from: d, to: d }
    },
  },
  {
    label: "7 дней",
    getDates: (): DateRange => {
      const to = yesterday()
      const from = new Date(to)
      from.setDate(from.getDate() - 6)
      return { from, to }
    },
  },
  {
    label: "28 дней",
    getDates: (): DateRange => {
      const to = yesterday()
      const from = new Date(to)
      from.setDate(from.getDate() - 27)
      return { from, to }
    },
  },
  {
    label: "Месяц",
    getDates: (): DateRange => {
      const to = yesterday()
      const from = new Date(to.getFullYear(), to.getMonth(), 1)
      return { from, to }
    },
  },
  {
    label: "Квартал",
    getDates: (): DateRange => {
      const to = yesterday()
      const from = new Date(to.getFullYear(), to.getMonth() - 2, 1)
      return { from, to }
    },
  },
  {
    label: "Год",
    getDates: (): DateRange => {
      const to = yesterday()
      const from = new Date(to.getFullYear(), 0, 1)
      return { from, to }
    },
  },
]

function formatDate(date: Date): string {
  return date.toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  })
}

interface DateRangePickerProps {
  value?: DateRange
  onChange: (range: DateRange | undefined) => void
  className?: string
}

export function DateRangePicker({
  value,
  onChange,
  className,
}: DateRangePickerProps) {
  const displayText =
    value?.from && value?.to
      ? `${formatDate(value.from)} — ${formatDate(value.to)}`
      : value?.from
        ? formatDate(value.from)
        : "Выберите период"

  return (
    <Popover>
      <PopoverTrigger
        className={cn(
          "flex items-center gap-1.5 bg-bg-soft border border-border rounded-md px-3 py-1.5 text-[12px] text-muted-foreground hover:bg-bg-hover hover:text-foreground transition-colors",
          className
        )}
      >
        <CalendarDays className="size-3.5" />
        {displayText}
      </PopoverTrigger>
      <PopoverContent align="start" className="w-auto p-0">
        <div className="flex">
          <div className="flex flex-col gap-0.5 border-r border-border p-2 min-w-[120px]">
            {presets.map((preset) => (
              <button
                key={preset.label}
                type="button"
                className="text-left text-[12px] hover:bg-bg-hover rounded px-2 py-1.5 text-muted-foreground hover:text-foreground transition-colors"
                onClick={() => onChange(preset.getDates())}
              >
                {preset.label}
              </button>
            ))}
          </div>
          <div className="p-2">
            <Calendar
              mode="range"
              selected={value}
              onSelect={onChange}
              numberOfMonths={2}
              weekStartsOn={1}
              locale={ru}
              disabled={{ after: yesterday() }}
            />
            <div className="flex justify-end px-2 pb-2">
              <button
                type="button"
                className="text-[11px] text-muted-foreground hover:text-foreground transition-colors"
                onClick={() => onChange(undefined)}
              >
                Сбросить
              </button>
            </div>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  )
}
