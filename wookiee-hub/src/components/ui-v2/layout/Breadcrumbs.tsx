import * as React from "react"
import { Link } from "react-router-dom"
import { ChevronRight } from "lucide-react"
import { cn } from "@/lib/utils"

export interface BreadcrumbItem {
  label: string
  href?: string
}

/**
 * Items can be either plain strings (canonical foundation.jsx:2092-2105
 * shape — `items: string[]`) or `{label, href?}` objects (our react-router
 * upgrade). Detected by inspecting the first element.
 */
export type BreadcrumbsItems = string[] | BreadcrumbItem[]

export interface BreadcrumbsProps extends React.HTMLAttributes<HTMLElement> {
  items: BreadcrumbsItems
}

function isStringItem(v: string | BreadcrumbItem): v is string {
  return typeof v === "string"
}

export const Breadcrumbs = React.forwardRef<HTMLElement, BreadcrumbsProps>(
  function Breadcrumbs({ items, className, ...rest }, ref) {
    return (
      <nav
        ref={ref}
        aria-label="Breadcrumb"
        className={cn("flex items-center gap-1.5 text-sm", className)}
        {...rest}
      >
        {items.map((item, idx) => {
          const isLast = idx === items.length - 1
          const label = isStringItem(item) ? item : item.label
          const href = isStringItem(item) ? undefined : item.href
          return (
            <React.Fragment key={`${label}-${idx}`}>
              {idx > 0 && (
                <ChevronRight
                  className="w-3 h-3 text-label shrink-0"
                  aria-hidden
                />
              )}
              {isLast ? (
                <span
                  className="text-primary font-medium truncate"
                  aria-current="page"
                >
                  {label}
                </span>
              ) : href ? (
                <Link
                  to={href}
                  className="text-muted hover:text-primary transition-colors truncate"
                >
                  {label}
                </Link>
              ) : (
                <span className="text-muted truncate">{label}</span>
              )}
            </React.Fragment>
          )
        })}
      </nav>
    )
  },
)
