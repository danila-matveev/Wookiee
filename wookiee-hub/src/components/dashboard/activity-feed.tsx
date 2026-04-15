import { cn } from "@/lib/utils"
import { activityEvents } from "@/data/dashboard-mock"

export function ActivityFeed({ className }: { className?: string }) {
  return (
    <div className={cn("bg-card border border-border rounded-[10px] p-4", className)}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold">Лента активности</h3>
        <button className="text-[12px] text-accent hover:underline">Все →</button>
      </div>
      <div className="flex flex-col gap-3">
        {activityEvents.map((event, i) => (
          <div key={i} className="flex items-start gap-2.5">
            <div
              className="w-[7px] h-[7px] rounded-full mt-1.5 shrink-0"
              style={{ backgroundColor: event.color }}
            />
            <div className="flex-1 min-w-0">
              <p className="text-[12px] leading-relaxed">{event.text}</p>
              <span className="text-[11px] text-text-dim">{event.time}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
