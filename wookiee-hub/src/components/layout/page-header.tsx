import type { ReactNode } from "react"
import { Link } from "react-router-dom"
import { ChevronRight } from "lucide-react"
import { cn } from "@/lib/utils"

export interface Crumb {
  label: string
  to: string
}

export interface PageHeaderProps {
  kicker?: string
  title: string
  breadcrumbs?: Crumb[]
  status?: ReactNode
  actions?: ReactNode
  description?: string
  className?: string
}

export function PageHeader({
  kicker,
  title,
  breadcrumbs,
  status,
  actions,
  description,
  className,
}: PageHeaderProps) {
  return (
    <header className={cn("border-b border-border pb-6 mb-6", className)}>
      {breadcrumbs && breadcrumbs.length > 0 && (
        <nav className="flex items-center gap-1 text-xs text-muted-foreground mb-3">
          {breadcrumbs.map((c, i) => (
            <span key={i} className="flex items-center gap-1">
              <Link to={c.to} className="hover:text-foreground">{c.label}</Link>
              {i < breadcrumbs.length - 1 && <ChevronRight className="size-3" />}
            </span>
          ))}
        </nav>
      )}
      <div className="flex items-start justify-between gap-4">
        <div>
          {kicker && (
            <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground mb-1">
              {kicker}
            </div>
          )}
          <h1 className="font-serif text-4xl font-light italic text-foreground">
            {title}
          </h1>
          {description && (
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground max-w-2xl">{description}</p>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {status}
          {actions}
        </div>
      </div>
    </header>
  )
}
