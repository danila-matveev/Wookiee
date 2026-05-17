import { Children, type ReactNode } from "react"
import { cn } from "@/lib/utils"

export interface AvatarGroupProps {
  children: ReactNode
  max?: number
  className?: string
}

export function AvatarGroup({ children, max, className }: AvatarGroupProps) {
  const kids = Children.toArray(children)
  const visible = max ? kids.slice(0, max) : kids
  const overflow = max ? Math.max(0, kids.length - max) : 0

  return (
    <div
      data-slot="avatar-group"
      className={cn("inline-flex -space-x-2", className)}
    >
      {visible}
      {overflow > 0 && (
        <span
          aria-label={`Ещё ${overflow}`}
          className="inline-flex items-center justify-center size-8 rounded-full bg-muted text-muted-foreground text-xs ring-2 ring-background"
        >
          +{overflow}
        </span>
      )}
    </div>
  )
}
