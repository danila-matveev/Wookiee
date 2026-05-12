import * as React from "react"
import { cn } from "@/lib/utils"

export interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {}

// Literal stone-200/800 per canonical (foundation.jsx:433) — surface-muted
// in dark drops to stone-900/40% which lacks contrast against stone-900 page.
export function Skeleton({ className, ...props }: SkeletonProps) {
  return (
    <div
      aria-busy="true"
      aria-live="polite"
      className={cn("animate-pulse rounded bg-stone-200 dark:bg-stone-800", className)}
      {...props}
    />
  )
}
