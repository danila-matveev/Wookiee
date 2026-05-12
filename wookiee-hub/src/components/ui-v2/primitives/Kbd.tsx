import * as React from "react"
import { cn } from "@/lib/utils"

export interface KbdProps extends React.HTMLAttributes<HTMLElement> {}

export const Kbd = React.forwardRef<HTMLElement, KbdProps>(function Kbd(
  { className, children, ...props },
  ref,
) {
  return (
    <kbd
      ref={ref}
      className={cn(
        "inline-flex items-center justify-center min-w-[1.25rem] h-5 px-1.5 text-[10px] font-mono font-medium",
        "rounded border border-default bg-surface-muted text-secondary",
        "shadow-[inset_0_-1px_0_var(--color-border-default)]",
        className,
      )}
      {...props}
    >
      {children}
    </kbd>
  )
})
