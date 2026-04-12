import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"

interface TableSkeletonProps {
  rows?: number
  className?: string
}

export function TableSkeleton({ rows = 5, className }: TableSkeletonProps) {
  return (
    <div
      className={cn(
        "bg-card border border-border rounded-[10px] p-4",
        className
      )}
    >
      <Skeleton className="h-4 w-24 mb-3" />
      {/* Header */}
      <div className="grid grid-cols-[1fr_auto_auto_auto] gap-x-4 pb-2 border-b border-border/50">
        <Skeleton className="h-3 w-16" />
        <Skeleton className="h-3 w-14" />
        <Skeleton className="h-3 w-8" />
        <Skeleton className="h-3 w-10" />
      </div>
      {/* Rows */}
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="grid grid-cols-[1fr_auto_auto_auto] gap-x-4 py-2 border-b border-border/20"
        >
          <Skeleton className="h-3 w-28" />
          <Skeleton className="h-3 w-14" />
          <Skeleton className="h-3 w-8" />
          <Skeleton className="h-3 w-10" />
        </div>
      ))}
    </div>
  )
}
