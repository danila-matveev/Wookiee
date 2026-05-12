import * as React from "react"
import { Check, ChevronDown, Search } from "lucide-react"
import { cn } from "@/lib/utils"
import { FieldWrap, describedBy } from "./FieldWrap"
import { inputBase, inputError, inputSizeMd } from "./_shared"

export interface SelectOption {
  value: string
  label: string
  disabled?: boolean
}

export interface SelectFieldProps {
  id: string
  label?: React.ReactNode
  hint?: React.ReactNode
  error?: React.ReactNode
  required?: boolean
  labelAddon?: React.ReactNode

  value: string | null
  onChange: (next: string) => void
  options: SelectOption[]
  placeholder?: string
  disabled?: boolean
  searchable?: boolean

  className?: string
  name?: string
}

export function SelectField({
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
  searchable = false,
  className,
  name,
}: SelectFieldProps) {
  const [open, setOpen] = React.useState(false)
  const [query, setQuery] = React.useState("")
  const [highlight, setHighlight] = React.useState(0)
  const rootRef = React.useRef<HTMLDivElement | null>(null)
  const aria = describedBy(id, hint, error)

  const selected = options.find((o) => o.value === value) ?? null

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

  React.useEffect(() => {
    if (open) {
      const idx = filtered.findIndex((o) => o.value === value)
      setHighlight(idx >= 0 ? idx : 0)
    }
  }, [open, filtered, value])

  const choose = (opt: SelectOption) => {
    if (opt.disabled) return
    onChange(opt.value)
    setOpen(false)
    setQuery("")
  }

  const handleKeyDown: React.KeyboardEventHandler<HTMLDivElement> = (e) => {
    if (disabled) return
    if (!open) {
      if (e.key === "Enter" || e.key === " " || e.key === "ArrowDown") {
        e.preventDefault()
        setOpen(true)
      }
      return
    }
    if (e.key === "Escape") {
      e.preventDefault()
      setOpen(false)
      setQuery("")
    } else if (e.key === "ArrowDown") {
      e.preventDefault()
      setHighlight((h) => Math.min(h + 1, filtered.length - 1))
    } else if (e.key === "ArrowUp") {
      e.preventDefault()
      setHighlight((h) => Math.max(h - 1, 0))
    } else if (e.key === "Enter") {
      e.preventDefault()
      const opt = filtered[highlight]
      if (opt) choose(opt)
    }
  }

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
      <div ref={rootRef} className="relative" onKeyDown={handleKeyDown}>
        <button
          id={id}
          type="button"
          name={name}
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
          <span className={cn(!selected && "text-muted")}>
            {selected ? selected.label : placeholder}
          </span>
          <ChevronDown
            className="w-3.5 h-3.5 absolute right-2.5 top-1/2 -translate-y-1/2 text-muted pointer-events-none"
            aria-hidden
          />
        </button>
        {open && (
          <div
            role="listbox"
            className={cn(
              "absolute z-[var(--z-dropdown)] mt-1 left-0 right-0 rounded-md overflow-hidden",
              "bg-elevated border border-default",
            )}
            style={{ boxShadow: "var(--shadow-md)" }}
          >
            {searchable && (
              <div className="p-2 border-b border-default">
                <div className="relative">
                  <Search
                    className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-muted pointer-events-none"
                    aria-hidden
                  />
                  <input
                    autoFocus
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Поиск…"
                    className={cn(inputBase, inputSizeMd, "pl-8")}
                  />
                </div>
              </div>
            )}
            <div className="max-h-56 overflow-y-auto py-1">
              {filtered.length === 0 ? (
                <div className="px-3 py-2 text-sm italic text-muted">
                  Ничего не найдено
                </div>
              ) : (
                filtered.map((opt, idx) => {
                  const active = opt.value === value
                  const highlighted = idx === highlight
                  return (
                    <button
                      key={opt.value}
                      type="button"
                      role="option"
                      aria-selected={active}
                      disabled={opt.disabled}
                      onMouseEnter={() => setHighlight(idx)}
                      onClick={() => choose(opt)}
                      className={cn(
                        "w-full px-3 py-1.5 text-sm text-left flex items-center justify-between",
                        "text-secondary",
                        highlighted && "bg-surface-muted",
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
