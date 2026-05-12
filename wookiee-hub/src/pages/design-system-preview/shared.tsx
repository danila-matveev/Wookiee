import type { ReactNode } from "react"
import { cn } from "@/lib/utils"

/**
 * <Demo> — the surface card every showcase block lives in.
 *
 * Canonical (`foundation.jsx:765-775`) — bordered top with UPPERCASE kicker
 * + optional mono `code` hint, then a padded body.
 *
 * In R5 we render `note` (right-aligned muted text) in place of the canonical
 * `code` slot. Where the canonical shows a code fragment, the note carries the
 * same role: a short usage hint.
 */
export interface DemoProps {
  title: string
  note?: string
  /** Stretch across all columns in the parent `DemoGrid`. */
  full?: boolean
  /** Remove the inner padding (useful for full-width tables, KPI grids). */
  padded?: boolean
  children: ReactNode
}

export function Demo({ title, note, full, padded = true, children }: DemoProps) {
  return (
    <section
      className={cn(
        "bg-elevated border border-default rounded-xl overflow-hidden",
        full && "col-span-full",
      )}
    >
      <header className="flex items-baseline justify-between gap-3 px-4 py-2 border-b border-default">
        <h3 className="text-[11px] uppercase tracking-wider font-medium text-muted">
          {title}
        </h3>
        {note ? (
          <span className="text-[10px] font-mono text-label">{note}</span>
        ) : null}
      </header>
      <div className={cn(padded ? "p-5" : "", "flex flex-wrap items-start gap-3")}>
        {children}
      </div>
    </section>
  )
}

/**
 * <DemoGrid> — single-column by default; pass `columns={2 | 3}` to mimic the
 * canonical `<Section columns={…}>` layout (foundation.jsx:751-762).
 */
export interface DemoGridProps {
  columns?: 1 | 2 | 3
  children: ReactNode
}

export function DemoGrid({ columns = 1, children }: DemoGridProps) {
  return (
    <div
      className={cn(
        "grid gap-4",
        columns === 2 && "grid-cols-1 md:grid-cols-2",
        columns === 3 && "grid-cols-1 md:grid-cols-3",
      )}
    >
      {children}
    </div>
  )
}

/**
 * <SubSection> — the canonical `<Section>` wrapper (foundation.jsx:751-762).
 *
 * Used inside section files to group related demo cards under an
 * italic-serif title + optional description.
 */
export interface SubSectionProps {
  title: string
  description?: string
  columns?: 1 | 2 | 3
  children: ReactNode
}

export function SubSection({ title, description, columns = 1, children }: SubSectionProps) {
  return (
    <section className="space-y-3">
      <div className="pb-2 border-b border-default">
        <h2 className="font-serif italic text-2xl text-primary">{title}</h2>
        {description && (
          <p className="text-sm text-muted mt-1 max-w-3xl">{description}</p>
        )}
      </div>
      <DemoGrid columns={columns}>{children}</DemoGrid>
    </section>
  )
}

/**
 * SubLabel — small uppercase row label used inside the Typography
 * demo (foundation.jsx:777-779).
 */
export function SubLabel({ children }: { children: ReactNode }) {
  return (
    <div className="text-[11px] uppercase tracking-wider font-medium mb-1.5 text-muted">
      {children}
    </div>
  )
}
