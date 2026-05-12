import * as React from "react"
import { Check, ChevronsUpDown, Search, X } from "lucide-react"
import { cn } from "@/lib/utils"
import { FieldWrap, describedBy } from "./FieldWrap"
import { inputBase, inputError, inputSizeMd } from "./_shared"
import type { SelectOption } from "./SelectField"
import type { CatalogLevel } from "../primitives"

interface NormalisedOption {
  value: string
  label: string
  disabled?: boolean
}

function normalise(opt: SelectOption): NormalisedOption {
  if ("value" in opt) {
    return { value: opt.value, label: opt.label, disabled: opt.disabled }
  }
  return { value: String(opt.id), label: opt.nazvanie, disabled: opt.disabled }
}

/**
 * Combobox mode:
 * - `input` (default, our upgrade): always-on text input + listbox.
 * - `button` (canonical, foundation.jsx:651-693): closed-state trigger
 *   button shows selected label + ChevronsUpDown; opening reveals a
 *   search Input inside the popover.
 */
export type ComboboxMode = "input" | "button"

export interface ComboboxProps {
  id: string
  label?: React.ReactNode
  hint?: React.ReactNode
  error?: React.ReactNode
  required?: boolean
  /** Catalog-hierarchy marker rendered inline with the label (M/V/A/S). */
  level?: CatalogLevel
  labelAddon?: React.ReactNode

  value: string | null
  onChange: (next: string | null) => void
  options: SelectOption[]
  placeholder?: string
  disabled?: boolean
  className?: string
  /** Allow clearing the selection via X button (default true). */
  clearable?: boolean
  /** Visual mode — see {@link ComboboxMode}. Default `input`. */
  mode?: ComboboxMode
}

export function Combobox({
  id,
  label,
  hint,
  error,
  required,
  level,
  labelAddon,
  value,
  onChange,
  options,
  placeholder = "Поиск…",
  disabled,
  className,
  clearable = true,
  mode = "input",
}: ComboboxProps) {
  const [open, setOpen] = React.useState(false)
  const [query, setQuery] = React.useState("")
  const [highlight, setHighlight] = React.useState(0)
  const rootRef = React.useRef<HTMLDivElement | null>(null)
  const inputRef = React.useRef<HTMLInputElement | null>(null)
  const popoverInputRef = React.useRef<HTMLInputElement | null>(null)
  const aria = describedBy(id, hint, error)

  const normalised = React.useMemo(() => options.map(normalise), [options])
  const selected = normalised.find((o) => o.value === value) ?? null

  const filtered = React.useMemo(() => {
    if (!query) return normalised
    const q = query.toLowerCase()
    return normalised.filter((o) => o.label.toLowerCase().includes(q))
  }, [normalised, query])

  React.useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false)
        setQuery("")
      }
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [open])

  React.useEffect(() => {
    if (mode === "button" && open) {
      window.requestAnimationFrame(() => popoverInputRef.current?.focus())
    }
  }, [mode, open])

  const choose = (opt: NormalisedOption) => {
    if (opt.disabled) return
    onChange(opt.value)
    setOpen(false)
    setQuery("")
  }

  const handleKeyDown: React.KeyboardEventHandler<HTMLInputElement> = (e) => {
    if (disabled) return
    if (!open && (e.key === "ArrowDown" || e.key === "Enter")) {
      e.preventDefault()
      setOpen(true)
      return
    }
    if (!open) return
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

  React.useEffect(() => {
    setHighlight(0)
  }, [query])

  const listbox = (
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
  )

  return (
    <FieldWrap
      id={id}
      label={label}
      hint={hint}
      error={error}
      required={required}
      level={level}
      labelAddon={labelAddon}
      className={className}
    >
      <div ref={rootRef} className="relative">
        {mode === "button" ? (
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
            <span className={cn(!selected && "text-muted")}>
              {selected ? selected.label : placeholder}
            </span>
            <ChevronsUpDown
              className="w-3.5 h-3.5 absolute right-2.5 top-1/2 -translate-y-1/2 text-muted pointer-events-none"
              aria-hidden
            />
          </button>
        ) : (
          <div className="relative">
            <input
              ref={inputRef}
              id={id}
              type="text"
              role="combobox"
              aria-expanded={open}
              aria-autocomplete="list"
              aria-invalid={error ? true : undefined}
              aria-describedby={aria}
              disabled={disabled}
              value={open ? query : (selected?.label ?? "")}
              placeholder={selected ? selected.label : placeholder}
              onChange={(e) => {
                setQuery(e.target.value)
                if (!open) setOpen(true)
              }}
              onFocus={() => !disabled && setOpen(true)}
              onKeyDown={handleKeyDown}
              className={cn(
                inputBase,
                inputSizeMd,
                "pr-14",
                error && inputError,
              )}
            />
            <div className="absolute right-1.5 top-1/2 -translate-y-1/2 flex items-center gap-0.5">
              {clearable && selected && !disabled ? (
                <button
                  type="button"
                  onClick={() => {
                    onChange(null)
                    setQuery("")
                    inputRef.current?.focus()
                  }}
                  className="p-1 rounded text-muted hover:text-primary hover:bg-surface-muted"
                  aria-label="Очистить"
                >
                  <X className="w-3 h-3" aria-hidden />
                </button>
              ) : null}
              <ChevronsUpDown className="w-3.5 h-3.5 text-muted pointer-events-none" aria-hidden />
            </div>
          </div>
        )}
        {open && (
          <div
            role="listbox"
            className={cn(
              "absolute z-[var(--z-dropdown)] mt-1 left-0 right-0 rounded-md overflow-hidden",
              "bg-elevated border border-default",
            )}
            style={{ boxShadow: "var(--shadow-md)" }}
          >
            {mode === "button" && (
              <div className="p-2 border-b border-default">
                <div className="relative">
                  <Search
                    className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-muted pointer-events-none"
                    aria-hidden
                  />
                  <input
                    ref={popoverInputRef}
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder={placeholder}
                    className={cn(inputBase, inputSizeMd, "pl-8")}
                  />
                </div>
              </div>
            )}
            {listbox}
          </div>
        )}
      </div>
    </FieldWrap>
  )
}
