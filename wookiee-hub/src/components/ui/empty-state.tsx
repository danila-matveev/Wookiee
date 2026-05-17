import type { ReactNode } from "react"
import { cn } from "@/lib/utils"

export interface EmptyStateProps {
  icon?: ReactNode
  title: string
  description?: string
  action?: ReactNode
  className?: string
}

export function EmptyState({ icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div
      data-slot="empty-state"
      className={cn(
        "flex flex-col items-center justify-center text-center py-12 px-4",
        className,
      )}
    >
      {icon && <div className="mb-4 text-muted-foreground">{icon}</div>}
      <h3 className="text-base font-medium text-foreground mb-1">{title}</h3>
      {description && <p className="text-sm text-muted-foreground mb-4 max-w-sm">{description}</p>}
      {action}
    </div>
  )
}
