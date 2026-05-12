import type { ReactNode } from "react"
import { LevelBadge } from "./level-badge"

export type FieldLevel = "model" | "variation" | "artikul" | "sku"

// Shared input styling using DS v2 semantic tokens.
// Keeps native <input>/<select>/<textarea> compatible with the existing
// catalog page-level props (readonly, mono, options as {id, nazvanie}, etc).
const INPUT_BASE =
  "w-full px-2.5 py-1.5 text-sm border border-default rounded-md bg-surface text-primary outline-none transition-colors " +
  "focus:border-strong focus:ring-1 focus:ring-[var(--color-ring)] placeholder:text-label"

// ─── FieldWrap ───────────────────────────────────────────────
interface FieldWrapProps {
  label: string
  level?: FieldLevel
  children: ReactNode
  full?: boolean
  hint?: string
}

export function FieldWrap({ label, level, children, full, hint }: FieldWrapProps) {
  return (
    <div className={full ? "col-span-2" : ""}>
      <div className="flex items-center gap-1.5 mb-1">
        <label className="block text-[11px] uppercase tracking-wider text-label">{label}</label>
        {level && <LevelBadge level={level} />}
      </div>
      {children}
      {hint && <div className="text-[10px] text-label mt-1">{hint}</div>}
    </div>
  )
}

// ─── TextField ───────────────────────────────────────────────
interface TextFieldProps {
  label: string
  value?: string | null
  onChange?: (v: string) => void
  placeholder?: string
  type?: string
  readonly?: boolean
  hint?: string
  mono?: boolean
  full?: boolean
  level?: FieldLevel
}

export function TextField({
  label, value, onChange, placeholder, type = "text",
  readonly, hint, mono, full, level,
}: TextFieldProps) {
  return (
    <FieldWrap label={label} level={level} full={full} hint={hint}>
      {readonly ? (
        <div className={`px-2.5 py-1.5 text-sm text-primary ${mono ? "font-mono" : ""}`}>
          {value || <span className="text-label italic">не задано</span>}
        </div>
      ) : (
        <input
          type={type}
          value={value ?? ""}
          onChange={(e) => onChange?.(e.target.value)}
          placeholder={placeholder}
          className={`${INPUT_BASE} ${mono ? "font-mono" : ""}`}
        />
      )}
    </FieldWrap>
  )
}

// ─── NumberField ─────────────────────────────────────────────
interface NumberFieldProps {
  label: string
  value?: number | null
  onChange?: (v: number) => void
  suffix?: string
  readonly?: boolean
  full?: boolean
  level?: FieldLevel
}

export function NumberField({ label, value, onChange, suffix, readonly, full, level }: NumberFieldProps) {
  return (
    <FieldWrap label={label} level={level} full={full}>
      {readonly ? (
        <div className="px-2.5 py-1.5 text-sm text-primary tabular-nums">
          {value != null ? (
            <>{value}{suffix && <span className="text-label ml-1">{suffix}</span>}</>
          ) : (
            <span className="text-label italic">не задано</span>
          )}
        </div>
      ) : (
        <div className="relative">
          <input
            type="number"
            value={value ?? ""}
            onChange={(e) => onChange?.(parseFloat(e.target.value) || 0)}
            className={`${INPUT_BASE} tabular-nums pr-10`}
          />
          {suffix && (
            <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-xs text-label">{suffix}</span>
          )}
        </div>
      )}
    </FieldWrap>
  )
}

// ─── SelectField ─────────────────────────────────────────────
interface SelectOption { id: number | string; nazvanie?: string; label?: string }

interface SelectFieldProps {
  label: string
  value?: number | string | null
  onChange?: (v: number | string) => void
  options: SelectOption[]
  placeholder?: string
  readonly?: boolean
  full?: boolean
  level?: FieldLevel
}

export function SelectField({
  label, value, onChange, options, placeholder = "Выберите…", readonly, full, level,
}: SelectFieldProps) {
  const selected = options.find((o) => o.id === value)
  return (
    <FieldWrap label={label} level={level} full={full}>
      {readonly ? (
        <div className="px-2.5 py-1.5 text-sm text-primary">
          {selected?.nazvanie ?? selected?.label ?? <span className="text-label italic">не задано</span>}
        </div>
      ) : (
        <select
          value={value ?? ""}
          onChange={(e) => onChange?.(isNaN(Number(e.target.value)) ? e.target.value : Number(e.target.value))}
          className={INPUT_BASE}
        >
          <option value="">{placeholder}</option>
          {options.map((o) => (
            <option key={o.id} value={o.id}>{o.nazvanie ?? o.label}</option>
          ))}
        </select>
      )}
    </FieldWrap>
  )
}

// ─── StringSelectField ───────────────────────────────────────
interface StringSelectFieldProps {
  label: string
  value?: string | null
  onChange?: (v: string) => void
  options: string[]
  readonly?: boolean
  full?: boolean
  level?: FieldLevel
}

export function StringSelectField({ label, value, onChange, options, readonly, full, level }: StringSelectFieldProps) {
  return (
    <FieldWrap label={label} level={level} full={full}>
      {readonly ? (
        <div className="px-2.5 py-1.5 text-sm text-primary">
          {value ?? <span className="text-label italic">не задано</span>}
        </div>
      ) : (
        <select
          value={value ?? ""}
          onChange={(e) => onChange?.(e.target.value)}
          className={INPUT_BASE}
        >
          <option value="">Выберите…</option>
          {options.map((o) => (
            <option key={o} value={o}>{o}</option>
          ))}
        </select>
      )}
    </FieldWrap>
  )
}

// ─── MultiSelectField ────────────────────────────────────────
interface MultiSelectFieldProps {
  label: string
  value?: string[]
  onChange?: (v: string[]) => void
  options: string[]
  readonly?: boolean
  full?: boolean
  level?: FieldLevel
}

export function MultiSelectField({ label, value = [], onChange, options, readonly, full, level }: MultiSelectFieldProps) {
  const toggle = (v: string) =>
    onChange?.(value.includes(v) ? value.filter((x) => x !== v) : [...value, v])

  return (
    <FieldWrap label={label} level={level} full={full}>
      <div className="flex flex-wrap gap-1.5">
        {options.map((o) => {
          const active = value.includes(o)
          return (
            <button
              key={o}
              disabled={readonly}
              onClick={() => toggle(o)}
              className={`px-2.5 py-1 text-xs rounded-md border transition-colors ${
                active
                  ? "bg-[var(--color-text-primary)] text-[var(--color-surface)] border-strong"
                  : "bg-surface border-default text-secondary hover:border-strong"
              } ${readonly ? "cursor-default" : ""}`}
            >
              {o}
            </button>
          )
        })}
      </div>
    </FieldWrap>
  )
}

// ─── TextareaField ───────────────────────────────────────────
interface TextareaFieldProps {
  label: string
  value?: string | null
  onChange?: (v: string) => void
  rows?: number
  readonly?: boolean
  full?: boolean
  level?: FieldLevel
}

export function TextareaField({ label, value, onChange, rows = 3, readonly, full = true, level }: TextareaFieldProps) {
  return (
    <FieldWrap label={label} level={level} full={full}>
      {readonly ? (
        <div className="px-2.5 py-1.5 text-sm text-primary whitespace-pre-wrap">
          {value ?? <span className="text-label italic">не задано</span>}
        </div>
      ) : (
        <textarea
          value={value ?? ""}
          rows={rows}
          onChange={(e) => onChange?.(e.target.value)}
          className={`${INPUT_BASE} resize-none`}
        />
      )}
    </FieldWrap>
  )
}
