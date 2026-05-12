import * as React from "react"
import { Link } from "react-router-dom"
import { ChevronRight } from "lucide-react"
import { cn } from "@/lib/utils"

export interface BreadcrumbItem {
  label: string
  href?: string
}

export interface BreadcrumbsProps extends React.HTMLAttributes<HTMLElement> {
  items: BreadcrumbItem[]
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
          return (
            <React.Fragment key={`${item.label}-${idx}`}>
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
                  {item.label}
                </span>
              ) : item.href ? (
                <Link
                  to={item.href}
                  className="text-muted hover:text-primary transition-colors truncate"
                >
                  {item.label}
                </Link>
              ) : (
                <span className="text-muted truncate">{item.label}</span>
              )}
            </React.Fragment>
          )
        })}
      </nav>
    )
  },
)
