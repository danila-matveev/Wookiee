import * as React from "react"
import { cn } from "@/lib/utils"

export interface PageHeaderProps extends React.HTMLAttributes<HTMLDivElement> {
  title: string
  description?: string
  actions?: React.ReactNode
  icon?: React.ReactNode
}

export const PageHeader = React.forwardRef<HTMLDivElement, PageHeaderProps>(
  function PageHeader(
    { title, description, actions, icon, className, ...rest },
    ref,
  ) {
    return (
      <div
        ref={ref}
        className={cn(
          "flex items-start justify-between gap-4 w-full",
          className,
        )}
        {...rest}
      >
        <div className="flex items-start gap-3 min-w-0">
          {icon && (
            <div className="shrink-0 flex items-center justify-center text-muted">
              {icon}
            </div>
          )}
          <div className="min-w-0">
            <h1 className="font-serif italic text-4xl leading-tight text-primary truncate">
              {title}
            </h1>
            {description && (
              <p className="mt-1 text-sm text-muted max-w-2xl">
                {description}
              </p>
            )}
          </div>
        </div>
        {actions && (
          <div className="shrink-0 flex items-center gap-2">{actions}</div>
        )}
      </div>
    )
  },
)
