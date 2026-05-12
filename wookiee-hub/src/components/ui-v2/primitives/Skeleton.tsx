import * as React from "react"
import { cn } from "@/lib/utils"

export interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {}

export function Skeleton({ className, ...props }: SkeletonProps) {
  return (
    <div
      aria-busy="true"
      aria-live="polite"
      className={cn("animate-pulse rounded-md bg-surface-muted", className)}
      {...props}
    />
  )
}
