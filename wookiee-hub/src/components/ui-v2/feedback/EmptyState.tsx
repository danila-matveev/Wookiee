import * as React from "react"
import { Inbox } from "lucide-react"
import { cn } from "@/lib/utils"

export interface EmptyStateProps {
  /** Icon shown above the title. Default: Inbox. */
  icon?: React.ReactNode
  title: string
  description?: string
  action?: React.ReactNode
  className?: string
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  const resolvedIcon =
    icon ?? <Inbox className="w-8 h-8" aria-hidden />

  return (
    <div
      className={cn(
        "flex flex-col items-center text-center py-10 px-4",
        className,
      )}
    >
      <div className="text-[color:var(--color-text-label)] mb-3">{resolvedIcon}</div>
      <div className="text-sm font-medium text-primary mb-1">{title}</div>
      {description && (
        <div className="text-xs italic text-muted max-w-sm mx-auto">
          {description}
        </div>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}
