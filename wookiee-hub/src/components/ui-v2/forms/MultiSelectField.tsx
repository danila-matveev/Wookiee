import * as React from "react"
import { Check, ChevronDown, X } from "lucide-react"
import { cn } from "@/lib/utils"
import { FieldWrap, describedBy } from "./FieldWrap"
import { inputBase, inputError, inputSizeMd } from "./_shared"
import type { SelectOption } from "./SelectField"

export interface MultiSelectFieldProps {
  id: string
  label?: React.ReactNode
  hint?: React.ReactNode
  error?: React.ReactNode
  required?: boolean
  labelAddon?: React.ReactNode

  value: string[]
  onChange: (next: string[]) => void
  options: SelectOption[]

  placeholder?: string
  disabled?: boolean
  searchable?: boolean
  className?: string
}

export function MultiSelectField({
  id,
  label,
  hint,
  error,
  required,
  labelAddon,
  value,
  onChange,
  options,
  placeholder = "Выберите…",
  disabled,
  searchable = true,
  className,
}: MultiSelectFieldProps) {
  const [open, setOpen] = React.useState(false)
  const [query, setQuery] = React.useState("")
  const rootRef = React.useRef<HTMLDivElement | null>(null)
  const aria = describedBy(id, hint, error)

  const selected = React.useMemo(
    () =>
      value
        .map((v) => options.find((o) => o.value === v))
        .filter((o): o is SelectOption => Boolean(o)),
    [value, options],
  )

  const filtered = React.useMemo(() => {
    if (!searchable || !query) return options
    const q = query.toLowerCase()
    return options.filter((o) => o.label.toLowerCase().includes(q))
  }, [options, searchable, query])

  React.useEffect(() => {
    if (!open) return
    const onDocMouseDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false)
        setQuery("")
      }
    }
    document.addEventListener("mousedown", onDocMouseDown)
    return () => document.removeEventListener("mousedown", onDocMouseDown)
  }, [open])

  const toggle = (v: string) => {
    if (value.includes(v)) onChange(value.filter((x) => x !== v))
    else onChange([...value, v])
  }

  const remove = (v: string) => onChange(value.filter((x) => x !== v))

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
        {selected.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-1.5">
            {selected.map((opt) => (
              <span
                key={opt.value}
                className={cn(
                  "inline-flex items-center gap-1 h-6 pl-2 pr-1 rounded text-xs",
                  "bg-surface-muted text-secondary border border-default",
                )}
              >
                {opt.label}
                <button
                  type="button"
                  disabled={disabled}
                  onClick={() => remove(opt.value)}
                  aria-label={`Удалить ${opt.label}`}
                  className="p-0.5 rounded hover:bg-surface text-muted hover:text-primary"
                >
                  <X className="w-3 h-3" aria-hidden />
                </button>
              </span>
            ))}
          </div>
        )}
        <button
          id={id}
          type="button"
          disabled={disabled}
          aria-haspopup="listbox"
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
          <span className={cn(selected.length === 0 && "text-muted")}>
            {selected.length === 0
              ? placeholder
              : `Выбрано: ${selected.length}`}
          </span>
          <ChevronDown
            className="w-3.5 h-3.5 absolute right-2.5 top-1/2 -translate-y-1/2 text-muted pointer-events-none"
            aria-hidden
          />
        </button>
        {open && (
          <div
            role="listbox"
            aria-multiselectable
            className={cn(
              "absolute z-[var(--z-dropdown)] mt-1 left-0 right-0 rounded-md overflow-hidden",
              "bg-elevated border border-default",
            )}
            style={{ boxShadow: "var(--shadow-md)" }}
          >
            {searchable && (
              <div className="p-2 border-b border-default">
                <input
                  autoFocus
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Поиск…"
                  className={cn(inputBase, inputSizeMd)}
                />
              </div>
            )}
            <div className="max-h-56 overflow-y-auto py-1">
              {filtered.length === 0 ? (
                <div className="px-3 py-2 text-sm italic text-muted">
                  Ничего не найдено
                </div>
              ) : (
                filtered.map((opt) => {
                  const active = value.includes(opt.value)
                  return (
                    <button
                      key={opt.value}
                      type="button"
                      role="option"
                      aria-selected={active}
                      disabled={opt.disabled}
                      onClick={() => toggle(opt.value)}
                      className={cn(
                        "w-full px-3 py-1.5 text-sm text-left flex items-center justify-between",
                        "text-secondary hover:bg-surface-muted",
                        active && "text-primary",
                        opt.disabled && "opacity-50 cursor-not-allowed",
                      )}
                    >
                      <span>{opt.label}</span>
                      {active && <Check className="w-3.5 h-3.5" aria-hidden />}
                    </button>
                  )
                })
              )}
            </div>
          </div>
        )}
      </div>
    </FieldWrap>
  )
}
