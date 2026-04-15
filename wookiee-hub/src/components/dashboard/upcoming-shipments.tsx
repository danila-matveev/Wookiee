import { cn } from "@/lib/utils"
import { StatusPill } from "@/components/shared/status-pill"
import { upcomingShipments } from "@/data/dashboard-mock"
import { formatNumber } from "@/lib/format"

export function UpcomingShipments({ className }: { className?: string }) {
  return (
    <div className={cn("bg-card border border-border rounded-[10px] p-4", className)}>
      <h3 className="text-sm font-semibold mb-3">Ближайшие поставки</h3>
      <div className="flex flex-col gap-2">
        {upcomingShipments.map((shipment) => (
          <div key={shipment.id} className="bg-background rounded-lg p-3 border border-border/50">
            <div className="flex items-center justify-between">
              <span className="text-accent text-[13px] font-mono font-semibold">{shipment.id}</span>
              <StatusPill label={shipment.status} color={shipment.statusColor} />
            </div>
            <div className="text-[18px] font-bold mt-1">{formatNumber(shipment.items)} шт</div>
            <div className="flex items-center justify-between mt-1">
              <span className="text-[12px] text-muted-foreground">{shipment.warehouse}</span>
              <span className="text-[12px] text-text-dim">{shipment.date}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
