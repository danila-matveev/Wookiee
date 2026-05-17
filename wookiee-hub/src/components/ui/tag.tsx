import type { ReactNode } from "react"
import { cn } from "@/lib/utils"

export interface TagProps {
  children: ReactNode
  className?: string
}

export function Tag({ children, className }: TagProps) {
  return (
    <span
      data-slot="tag"
      className={cn(
        "inline-flex items-center rounded-md bg-secondary text-secondary-foreground px-2 py-0.5 text-xs",
        className,
      )}
    >
      {children}
    </span>
  )
}
