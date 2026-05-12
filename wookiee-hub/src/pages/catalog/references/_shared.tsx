import { useEffect, useRef, useState, type ReactNode } from "react"
import { MoreHorizontal, Pencil, Plus, Trash2, Search } from "lucide-react"

// ─── Re-export atomic RefModal (Wave 1) ────────────────────────────────────
//
// Pages should `import { RefModal } from "./_shared"` to get the shared
// extended modal with text/number/textarea/select/multiselect/file_url/date/
// checkbox support.
export { RefModal } from "@/components/catalog/ui/ref-modal"
export type {
  RefFieldDef,
  RefFieldType,
  RefFieldOption,
} from "@/components/catalog/ui/ref-modal"

// ─── Page header ───────────────────────────────────────────────────────────

interface PageHeaderProps {
  title: string
  /** Subtitle shown right under the H1 — describes what this reference is. */
  subtitle?: string
  count: number
  isLoading: boolean
  /**
   * Action buttons rendered to the right of the metadata block.
   * Typically the «+ Добавить» button.
   */
  actions?: ReactNode
}

export function PageHeader({
  title,
  subtitle,
  count,
  isLoading,
  actions,
}: PageHeaderProps) {
  return (
    <div className="mb-5">
      <div className="text-[11px] uppercase tracking-wider text-label mb-1">
        Справочник
      </div>
      <div className="flex items-end justify-between gap-4">
        <div className="min-w-0">
          <h1
            className="text-3xl text-primary italic"
            style={{ fontFamily: "'Instrument Serif', ui-serif, Georgia, serif" }}
          >
            {title}
          </h1>
          {subtitle && (
            <p className="text-sm text-muted mt-1 max-w-2xl">{subtitle}</p>
          )}
        </div>
        <div className="flex items-center gap-3 shrink-0">
          {isLoading ? (
            <span className="text-sm text-label">Загрузка…</span>
          ) : (
            <span className="text-sm text-muted tabular-nums">
              {count} записей
            </span>
          )}
          {actions}
        </div>
      </div>
    </div>
  )
}

// ─── Add button + Search ───────────────────────────────────────────────────

interface AddButtonProps {
  onClick: () => void
  label?: string
}

export function AddButton({ onClick, label = "Добавить" }: AddButtonProps) {
  return (
    <button
      onClick={onClick}
      className="px-3 py-1.5 text-xs text-[var(--color-surface)] bg-[var(--color-text-primary)] hover:opacity-90 rounded-md flex items-center gap-1.5 transition-colors"
    >
      <Plus className="w-3.5 h-3.5" /> {label}
    </button>
  )
}

interface SearchBoxProps {
  value: string
  onChange: (v: string) => void
  placeholder?: string
}

export function SearchBox({ value, onChange, placeholder = "Поиск…" }: SearchBoxProps) {
  return (
    <div className="relative mb-4">
      <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-label pointer-events-none" />
      <input
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full max-w-md pl-8 pr-3 py-1.5 text-sm border border-default rounded-md bg-surface text-primary outline-none focus:border-strong placeholder:text-label"
      />
    </div>
  )
}

// ─── Error / Skeleton ──────────────────────────────────────────────────────

interface ErrorBlockProps {
  message: string
}

export function ErrorBlock({ message }: ErrorBlockProps) {
  return (
    <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
      Ошибка загрузки: {message}
    </div>
  )
}

export function SkeletonTable({
  rows = 5,
  cols = 3,
}: {
  rows?: number
  cols?: number
}) {
  return (
    <div className="bg-surface rounded-lg border border-default overflow-hidden">
      <div className="bg-surface-muted/80 border-b border-default px-3 py-2.5 flex gap-6">
        {Array.from({ length: cols }).map((_, i) => (
          <div
            key={i}
            className="h-3 bg-surface-muted rounded animate-pulse"
            style={{ width: `${60 + i * 20}px` }}
          />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="flex gap-6 px-3 py-3 border-b border-subtle last:border-0"
        >
          {Array.from({ length: cols }).map((_, j) => (
            <div
              key={j}
              className="h-3 bg-surface-muted rounded animate-pulse"
              style={{ width: `${80 + j * 30}px` }}
            />
          ))}
        </div>
      ))}
    </div>
  )
}

// ─── Row actions (Edit / Delete) ──────────────────────────────────────────
//
// Renders a small button with a trailing dropdown menu. Designed to be placed
// in the last column of every reference table.

interface RowActionsProps {
  onEdit: () => void
  onDelete: () => void
}

export function RowActions({ onEdit, onDelete }: RowActionsProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false)
    }
    document.addEventListener("mousedown", onClick)
    document.addEventListener("keydown", onKey)
    return () => {
      document.removeEventListener("mousedown", onClick)
      document.removeEventListener("keydown", onKey)
    }
  }, [open])

  return (
    <div className="relative inline-block" ref={ref}>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation()
          setOpen((v) => !v)
        }}
        className="p-1 rounded hover:bg-surface-muted/60 text-label hover:text-primary opacity-40 group-hover:opacity-100 focus:opacity-100 transition-opacity"
        aria-label="Действия"
      >
        <MoreHorizontal className="w-4 h-4" />
      </button>
      {open && (
        <div className="absolute right-0 top-7 z-20 min-w-[140px] py-1 bg-surface border border-default rounded-md shadow-lg">
          <button
            type="button"
            onClick={() => {
              setOpen(false)
              onEdit()
            }}
            className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-secondary hover:bg-surface-muted text-left"
          >
            <Pencil className="w-3.5 h-3.5" /> Редактировать
          </button>
          <button
            type="button"
            onClick={() => {
              setOpen(false)
              onDelete()
            }}
            className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-danger hover:bg-danger-soft text-left"
          >
            <Trash2 className="w-3.5 h-3.5" /> Удалить
          </button>
        </div>
      )}
    </div>
  )
}

// ─── Confirm dialog (delete confirmation) ────────────────────────────────

interface ConfirmDialogProps {
  open: boolean
  title: string
  message?: string
  confirmLabel?: string
  cancelLabel?: string
  onConfirm: () => void | Promise<void>
  onCancel: () => void
  destructive?: boolean
}

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = "Удалить",
  cancelLabel = "Отмена",
  onConfirm,
  onCancel,
  destructive = true,
}: ConfirmDialogProps) {
  const [busy, setBusy] = useState(false)
  if (!open) return null

  const handleConfirm = async () => {
    setBusy(true)
    try {
      await onConfirm()
    } finally {
      setBusy(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 bg-[var(--color-text-primary)]/40 flex items-center justify-center p-4"
      onClick={onCancel}
    >
      <div
        className="w-full max-w-sm bg-surface rounded-xl shadow-2xl border border-default overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-5 py-4 border-b border-default">
          <h3 className="text-base font-medium text-primary">{title}</h3>
          {message && <p className="text-xs text-muted mt-1">{message}</p>}
        </div>
        <div className="flex items-center justify-end gap-2 px-5 py-3 bg-surface-muted">
          <button
            type="button"
            onClick={onCancel}
            className="px-3 py-1.5 text-sm text-secondary hover:bg-surface-muted/60 rounded-md"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={busy}
            className={
              destructive
                ? "px-3 py-1.5 text-sm text-white bg-[var(--color-danger)] hover:opacity-90 rounded-md disabled:opacity-50"
                : "px-3 py-1.5 text-sm text-[var(--color-surface)] bg-[var(--color-text-primary)] hover:opacity-90 rounded-md disabled:opacity-50"
            }
          >
            {busy ? "…" : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── PageShell (wraps every reference page consistently) ─────────────────

interface PageShellProps {
  children: ReactNode
}

export function PageShell({ children }: PageShellProps) {
  return <div className="px-6 py-6 max-w-6xl">{children}</div>
}
