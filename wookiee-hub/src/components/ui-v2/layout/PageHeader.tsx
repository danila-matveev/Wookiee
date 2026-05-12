import * as React from "react"
import { cn } from "@/lib/utils"
import { Breadcrumbs, type BreadcrumbsItems } from "./Breadcrumbs"

export interface PageHeaderProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Main page title — Instrument Serif italic text-3xl per DS. */
  title: string
  /**
   * UPPERCASE eyebrow above the title (e.g. "МОДЕЛЬ").
   * Canonical (foundation.jsx:2132-2146): text-[11px] uppercase tracking-wider text-label.
   */
  kicker?: string
  /** Breadcrumbs strip rendered above title (uses Breadcrumbs primitive). */
  breadcrumbs?: BreadcrumbsItems
  /** Inline status slot next to title (e.g. <StatusBadge />). */
  status?: React.ReactNode
  /** Right-aligned action group. */
  actions?: React.ReactNode

  /** @deprecated extension — prefer `kicker` + status. Optional icon left of title. */
  icon?: React.ReactNode
  /** @deprecated extension — kept for back-compat. Description sentence below title. */
  description?: string
}

export const PageHeader = React.forwardRef<HTMLDivElement, PageHeaderProps>(
  function PageHeader(
    {
      title,
      kicker,
      breadcrumbs,
      status,
      actions,
      icon,
      description,
      className,
      ...rest
    },
    ref,
  ) {
    return (
      <header
        ref={ref}
        className={cn(
          "flex items-start justify-between gap-6 pb-4 w-full",
          className,
        )}
        {...rest}
      >
        <div className="min-w-0 flex-1">
          {kicker && (
            <div className="text-[11px] uppercase tracking-wider text-label mb-0.5">
              {kicker}
            </div>
          )}
          <div className="flex items-center gap-3">
            {icon && (
              <div className="shrink-0 flex items-center justify-center text-muted">
                {icon}
              </div>
            )}
            <h1 className="font-serif italic text-3xl leading-tight text-primary truncate">
              {title}
            </h1>
            {status && <div className="shrink-0">{status}</div>}
          </div>
          {breadcrumbs && breadcrumbs.length > 0 && (
            <div className="mt-1.5">
              <Breadcrumbs items={breadcrumbs} />
            </div>
          )}
          {description && (
            <p className="mt-1 text-sm text-muted max-w-2xl">{description}</p>
          )}
        </div>
        {actions && (
          <div className="shrink-0 flex items-center gap-2">{actions}</div>
        )}
      </header>
    )
  },
)
