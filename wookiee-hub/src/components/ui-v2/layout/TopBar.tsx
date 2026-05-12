import * as React from "react"
import { cn } from "@/lib/utils"
import { Breadcrumbs, type BreadcrumbItem } from "./Breadcrumbs"

export interface TopBarProps extends React.HTMLAttributes<HTMLElement> {
  breadcrumbs?: BreadcrumbItem[]
  actions?: React.ReactNode
}

export const TopBar = React.forwardRef<HTMLElement, TopBarProps>(
  function TopBar(
    { breadcrumbs, actions, className, children, ...rest },
    ref,
  ) {
    return (
      <header
        ref={ref}
        className={cn(
          "h-14 px-6 border-b border-default bg-surface",
          "flex items-center justify-between gap-4",
          "sticky top-0 z-[var(--z-sticky,20)]",
          className,
        )}
        {...rest}
      >
        <div className="flex items-center gap-3 min-w-0">
          {breadcrumbs && breadcrumbs.length > 0 && (
            <Breadcrumbs items={breadcrumbs} />
          )}
        </div>

        {children !== undefined && (
          <div className="flex-1 flex items-center justify-center min-w-0">
            {children}
          </div>
        )}

        {actions && (
          <div className="flex items-center gap-2 shrink-0">{actions}</div>
        )}
      </header>
    )
  },
)
