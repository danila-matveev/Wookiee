import type { ReactNode } from "react"
import { X } from "lucide-react"
import { cn } from "@/lib/utils"

export interface ChipProps {
  children: ReactNode
  onRemove?: () => void
  className?: string
}

export function Chip({ children, onRemove, className }: ChipProps) {
  return (
    <span
      data-slot="chip"
      className={cn(
        "inline-flex items-center gap-1 rounded-full bg-secondary text-secondary-foreground px-2 py-0.5 text-xs",
        className,
      )}
    >
      {children}
      {onRemove && (
        <button
          type="button"
          onClick={onRemove}
          className="hover:bg-muted rounded-full p-0.5"
          aria-label="remove"
        >
          <X className="size-3" />
        </button>
      )}
    </span>
  )
}
