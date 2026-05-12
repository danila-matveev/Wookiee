import * as React from "react"
import { Calendar, ChevronLeft, ChevronRight } from "lucide-react"
import { cn } from "@/lib/utils"
import { FieldWrap, describedBy } from "./FieldWrap"
import { inputBase, inputError, inputSizeMd } from "./_shared"

export interface DatePickerProps {
  id: string
  label?: React.ReactNode
  hint?: React.ReactNode
  error?: React.ReactNode
  required?: boolean
  labelAddon?: React.ReactNode

  value: Date | null
  onChange: (next: Date | null) => void

  min?: Date
  max?: Date
  placeholder?: string
  disabled?: boolean
  className?: string
}

const MONTHS = [
  "Январь",
  "Февраль",
  "Март",
  "Апрель",
  "Май",
  "Июнь",
  "Июль",
  "Август",
  "Сентябрь",
  "Октябрь",
  "Ноябрь",
  "Декабрь",
]
const DAYS = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]

function pad(n: number): string {
  return String(n).padStart(2, "0")
}

function formatDisplay(d: Date | null): string {
  if (!d) return ""
  return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()}`
}

function isSameDay(a: Date | null | undefined, b: Date | null | undefined): boolean {
  if (!a || !b) return false
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  )
}

function outOfRange(d: Date, min?: Date, max?: Date): boolean {
  if (min && d < startOfDay(min)) return true
  if (max && d > endOfDay(max)) return true
  return false
}

function startOfDay(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate())
}

function endOfDay(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate(), 23, 59, 59, 999)
}

export function DatePicker({
  id,
  label,
  hint,
  error,
  required,
  labelAddon,
  value,
  onChange,
  min,
  max,
  placeholder = "Выберите дату",
  disabled,
  className,
}: DatePickerProps) {
  const [open, setOpen] = React.useState(false)
  const [view, setView] = React.useState<Date>(() => value ?? new Date())
  const rootRef = React.useRef<HTMLDivElement | null>(null)
  const aria = describedBy(id, hint, error)

  React.useEffect(() => {
    if (value) setView(value)
  }, [value])

  React.useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [open])

  const firstOfMonth = new Date(view.getFullYear(), view.getMonth(), 1)
  const startWeekday = (firstOfMonth.getDay() + 6) % 7 // Monday-first
  const lastDay = new Date(view.getFullYear(), view.getMonth() + 1, 0).getDate()
  const today = new Date()

  const cells: Array<Date | null> = []
  for (let i = 0; i < startWeekday; i++) cells.push(null)
  for (let d = 1; d <= lastDay; d++) {
    cells.push(new Date(view.getFullYear(), view.getMonth(), d))
  }
  while (cells.length % 7 !== 0) cells.push(null)

  return (
    <FieldWrap
      id={id}
      label={label}
      hint={hint}
      error={error}
      required={required}
      labelAddon={labelAddon}
      className={className}
    >
      <div ref={rootRef} className="relative">
        <button
          id={id}
          type="button"
          disabled={disabled}
          aria-haspopup="dialog"
          aria-expanded={open}
          aria-invalid={error ? true : undefined}
          aria-describedby={aria}
          onClick={() => !disabled && setOpen((v) => !v)}
          className={cn(
            inputBase,
            inputSizeMd,
            "flex items-center justify-between text-left pr-8",
            error && inputError,
          )}
        >
          <span className={cn(!value && "text-muted", value && "tabular-nums")}>
            {value ? formatDisplay(value) : placeholder}
          </span>
          <Calendar
            className="w-3.5 h-3.5 absolute right-2.5 top-1/2 -translate-y-1/2 text-muted pointer-events-none"
            aria-hidden
          />
        </button>
        {open && (
          <div
            role="dialog"
            className={cn(
              "absolute z-[var(--z-dropdown)] mt-1 left-0 rounded-lg p-3 w-72",
              "bg-elevated border border-default",
            )}
            style={{ boxShadow: "var(--shadow-md)" }}
          >
            <div className="flex items-center justify-between mb-2">
              <button
                type="button"
                onClick={() =>
                  setView(
                    new Date(view.getFullYear(), view.getMonth() - 1, 1),
                  )
                }
                className="p-1 rounded hover:bg-surface-muted text-secondary"
                aria-label="Предыдущий месяц"
              >
                <ChevronLeft className="w-3.5 h-3.5" aria-hidden />
              </button>
              <span className="text-sm font-medium text-primary">
                {MONTHS[view.getMonth()]} {view.getFullYear()}
              </span>
              <button
                type="button"
                onClick={() =>
                  setView(
                    new Date(view.getFullYear(), view.getMonth() + 1, 1),
                  )
                }
                className="p-1 rounded hover:bg-surface-muted text-secondary"
                aria-label="Следующий месяц"
              >
                <ChevronRight className="w-3.5 h-3.5" aria-hidden />
              </button>
            </div>
            <div className="grid grid-cols-7 gap-0.5 mb-1">
              {DAYS.map((d) => (
                <div
                  key={d}
                  className="text-center text-[10px] uppercase tracking-wider py-1 text-label"
                >
                  {d}
                </div>
              ))}
            </div>
            <div className="grid grid-cols-7 gap-0.5">
              {cells.map((d, i) => {
                if (!d) return <div key={i} />
                const isToday = isSameDay(d, today)
                const isSelected = isSameDay(d, value)
                const disabledCell = outOfRange(d, min, max)
                return (
                  <button
                    key={i}
                    type="button"
                    disabled={disabledCell}
                    onClick={() => {
                      onChange(d)
                      setOpen(false)
                    }}
                    className={cn(
                      "aspect-square text-xs rounded transition-colors tabular-nums",
                      isSelected
                        ? "bg-accent text-[var(--color-accent-text)] font-medium"
                        : isToday
                          ? "ring-1 ring-[var(--color-border-strong)] text-primary"
                          : "text-secondary hover:bg-surface-muted",
                      disabledCell && "opacity-30 cursor-not-allowed",
                    )}
                  >
                    {d.getDate()}
                  </button>
                )
              })}
            </div>
            <div className="mt-2 flex items-center justify-between">
              <button
                type="button"
                onClick={() => {
                  onChange(null)
                  setOpen(false)
                }}
                className="text-xs text-muted hover:text-primary"
              >
                Очистить
              </button>
              <button
                type="button"
                onClick={() => {
                  onChange(startOfDay(new Date()))
                  setOpen(false)
                }}
                className="text-xs text-accent hover:underline"
              >
                Сегодня
              </button>
            </div>
          </div>
        )}
      </div>
    </FieldWrap>
  )
}
