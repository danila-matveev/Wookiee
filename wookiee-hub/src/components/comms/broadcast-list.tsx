import { Trash2, Radio } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { getServiceDef } from "@/config/service-registry"
import type { Broadcast, BroadcastStatus } from "@/types/comms-broadcasts"

const statusConfig: Record<
  BroadcastStatus,
  { label: string; className: string }
> = {
  draft: {
    label: "Черновик",
    className: "bg-muted text-muted-foreground",
  },
  scheduled: {
    label: "Запланирована",
    className: "bg-blue-500/10 text-blue-600 dark:text-blue-400",
  },
  sent: {
    label: "Отправлена",
    className: "bg-green-500/10 text-green-600 dark:text-green-400",
  },
  error: {
    label: "Ошибка",
    className: "bg-red-500/10 text-red-600 dark:text-red-400",
  },
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  })
}

interface BroadcastListProps {
  broadcasts: Broadcast[]
  onDelete: (id: string) => void
}

export function BroadcastList({ broadcasts, onDelete }: BroadcastListProps) {
  if (broadcasts.length === 0) {
    return null
  }

  return (
    <div className="bg-card border border-border rounded-[10px] overflow-hidden">
      {/* Table header */}
      <div className="grid grid-cols-[1fr_140px_100px_110px_120px_48px] gap-3 px-4 py-2.5 border-b border-border text-[12px] font-medium text-muted-foreground uppercase tracking-wide">
        <span>Название</span>
        <span>Магазин</span>
        <span>Получатели</span>
        <span>Статус</span>
        <span>Дата</span>
        <span />
      </div>

      {/* Rows */}
      {broadcasts.map((broadcast) => {
        const svc = getServiceDef(broadcast.serviceType)
        const status = statusConfig[broadcast.status]

        return (
          <div
            key={broadcast.id}
            className="grid grid-cols-[1fr_140px_100px_110px_120px_48px] gap-3 px-4 py-3 border-b border-border last:border-b-0 items-center hover:bg-muted/30 transition-colors"
          >
            {/* Name */}
            <div className="flex items-center gap-2 min-w-0">
              <Radio className="size-4 text-muted-foreground shrink-0" />
              <span className="text-[13px] font-medium truncate">
                {broadcast.name}
              </span>
            </div>

            {/* Store badge */}
            <div>
              <span
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium text-white"
                style={{ backgroundColor: svc.color }}
              >
                {svc.label}
              </span>
            </div>

            {/* Recipients */}
            <span className="text-[13px] text-muted-foreground">
              {broadcast.recipientCount}
            </span>

            {/* Status */}
            <div>
              <span
                className={cn(
                  "inline-flex px-2 py-0.5 rounded-md text-[11px] font-medium",
                  status.className
                )}
              >
                {status.label}
              </span>
            </div>

            {/* Date */}
            <span className="text-[12px] text-muted-foreground">
              {formatDate(broadcast.createdAt)}
            </span>

            {/* Actions */}
            <div className="flex justify-end">
              <Button
                variant="ghost"
                size="icon-xs"
                onClick={() => onDelete(broadcast.id)}
                className="text-muted-foreground hover:text-destructive"
              >
                <Trash2 className="size-3.5" />
              </Button>
            </div>
          </div>
        )
      })}
    </div>
  )
}
