import * as React from "react"
import { cn } from "@/lib/utils"

export interface KbdProps extends React.HTMLAttributes<HTMLElement> {}

// Canonical Kbd is flat — no inset shadow, no min-width clamp.
// foundation.jsx:437-444.
export const Kbd = React.forwardRef<HTMLElement, KbdProps>(function Kbd(
  { className, children, ...props },
  ref,
) {
  return (
    <kbd
      ref={ref}
      className={cn(
        "inline-flex items-center justify-center rounded border border-default bg-surface-muted text-muted",
        "text-[10px] font-mono px-1.5 py-0.5 leading-none",
        className,
      )}
      {...props}
    >
      {children}
    </kbd>
  )
})
