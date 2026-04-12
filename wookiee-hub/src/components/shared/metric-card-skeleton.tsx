import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"

export function MetricCardSkeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "bg-card border border-border rounded-[10px] p-4",
        className
      )}
    >
      <Skeleton className="h-3 w-20 mb-3" />
      <Skeleton className="h-6 w-32 mb-2" />
      <Skeleton className="h-3 w-24" />
      <div className="mt-3 space-y-1">
        <Skeleton className="h-1 w-full" />
        <div className="flex justify-between">
          <Skeleton className="h-3 w-16" />
          <Skeleton className="h-3 w-20" />
        </div>
      </div>
    </div>
  )
}
