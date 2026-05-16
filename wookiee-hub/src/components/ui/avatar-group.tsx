import type { ReactNode } from "react"
import { cn } from "@/lib/utils"

export interface AvatarGroupProps {
  children: ReactNode
  max?: number
  className?: string
}

export function AvatarGroup({ children, max, className }: AvatarGroupProps) {
  return (
    <div
      data-slot="avatar-group"
      className={cn("inline-flex -space-x-2", className)}
    >
      {children}
    </div>
  )
}
