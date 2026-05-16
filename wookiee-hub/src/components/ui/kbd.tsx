import type { ReactNode } from "react"
import { cn } from "@/lib/utils"

export interface KbdProps {
  children?: ReactNode
  keys?: string[]
  className?: string
}

export function Kbd({ children, keys, className }: KbdProps) {
  if (keys) {
    return (
      <span data-slot="kbd-combo" className="inline-flex items-center gap-1">
        {keys.map((k, i) => (
          <kbd
            key={i}
            data-slot="kbd"
            className={cn(
              "inline-flex items-center justify-center min-w-5 h-5 px-1 rounded border border-border bg-muted text-muted-foreground font-mono text-[10px]",
              className,
            )}
          >
            {k}
          </kbd>
        ))}
      </span>
    )
  }
  return (
    <kbd
      data-slot="kbd"
      className={cn(
        "inline-flex items-center justify-center min-w-5 h-5 px-1 rounded border border-border bg-muted text-muted-foreground font-mono text-[10px]",
        className,
      )}
    >
      {children}
    </kbd>
  )
}
