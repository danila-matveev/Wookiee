// ---------------------------------------------------------------------------
// Supply Timeline — simple Gantt-like view of supply orders
// ---------------------------------------------------------------------------

import { useMemo } from "react"
import { useSupplyStore } from "@/stores/supply"
import { differenceInCalendarDays, parseISO, format } from "date-fns"
import { ru } from "date-fns/locale"

const STATUS_COLORS: Record<string, string> = {
  delivered: "bg-emerald-500",
  shipped: "bg-blue-500",
  ordered: "bg-violet-500",
  draft: "bg-zinc-400 dark:bg-zinc-600",
}

const STATUS_LABELS: Record<string, string> = {
  delivered: "Доставлен",
  shipped: "В пути",
  ordered: "Заказан",
  draft: "Черновик",
}

export function SupplyTimeline() {
  const orders = useSupplyStore((s) => s.orders)

  const visibleOrders = useMemo(
    () => orders.filter((o) => o.status !== "archived"),
    [orders],
  )

  const { minDate, totalDays } = useMemo(() => {
    if (visibleOrders.length === 0) {
      const now = new Date()
      return { minDate: now, totalDays: 1 }
    }

    let min = Infinity
    let max = -Infinity

    for (const order of visibleOrders) {
      const orderTs = parseISO(order.order_date).getTime()
      const deliveryTs = parseISO(order.delivery_date).getTime()
      if (orderTs < min) min = orderTs
      if (deliveryTs > max) max = deliveryTs
    }

    // Include today in the range
    const nowTs = new Date().getTime()
    if (nowTs < min) min = nowTs
    if (nowTs > max) max = nowTs

    // Add padding: 7 days on each side
    const padding = 7 * 24 * 60 * 60 * 1000
    const minD = new Date(min - padding)
    const maxD = new Date(max + padding)

    return {
      minDate: minD,
      totalDays: Math.max(differenceInCalendarDays(maxD, minD), 1),
    }
  }, [visibleOrders])

  // Today marker position as percentage
  const todayOffset = useMemo(() => {
    const days = differenceInCalendarDays(new Date(), minDate)
    return Math.max(0, Math.min(100, (days / totalDays) * 100))
  }, [minDate, totalDays])

  if (visibleOrders.length === 0) {
    return (
      <div className="flex items-center justify-center py-16 text-sm text-muted-foreground">
        Нет активных поставок для отображения
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Legend */}
      <div className="flex items-center gap-4 text-xs text-muted-foreground">
        {Object.entries(STATUS_COLORS).map(([status, colorClass]) => (
          <div key={status} className="flex items-center gap-1.5">
            <span className={`inline-block h-2.5 w-2.5 rounded-sm ${colorClass}`} />
            {STATUS_LABELS[status] ?? status}
          </div>
        ))}
        <div className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-0.5 bg-red-500" />
          Сегодня
        </div>
      </div>

      {/* Timeline grid */}
      <div className="overflow-x-auto rounded-lg border border-border">
        <div className="min-w-[600px]">
          {/* Month headers */}
          <MonthHeaders minDate={minDate} totalDays={totalDays} />

          {/* Rows */}
          <div className="relative">
            {/* Today marker */}
            <div
              className="absolute top-0 bottom-0 w-0.5 bg-red-500 z-10"
              style={{ left: `${todayOffset}%` }}
            />

            {visibleOrders.map((order) => {
              const startDays = differenceInCalendarDays(
                parseISO(order.order_date),
                minDate,
              )
              const endDays = differenceInCalendarDays(
                parseISO(order.delivery_date),
                minDate,
              )
              const leftPct = (startDays / totalDays) * 100
              const widthPct = Math.max(
                ((endDays - startDays) / totalDays) * 100,
                1,
              )

              const colorClass = STATUS_COLORS[order.status] ?? STATUS_COLORS.draft

              return (
                <div
                  key={order.id}
                  className="relative h-10 border-b border-border last:border-b-0"
                >
                  <div
                    className={`absolute top-1.5 h-7 rounded-md flex items-center px-2 text-xs font-medium text-white truncate shadow-sm ${colorClass}`}
                    style={{
                      left: `${leftPct}%`,
                      width: `${widthPct}%`,
                      minWidth: "60px",
                    }}
                    title={`${order.name} | ${format(parseISO(order.order_date), "dd MMM", { locale: ru })} — ${format(parseISO(order.delivery_date), "dd MMM", { locale: ru })}`}
                  >
                    {order.name}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Month headers ───────────────────────────────────────────────────────────

function MonthHeaders({
  minDate,
  totalDays,
}: {
  minDate: Date
  totalDays: number
}) {
  const months = useMemo(() => {
    const result: { label: string; leftPct: number; widthPct: number }[] = []
    const start = new Date(minDate)
    start.setDate(1) // first of the month

    const endDate = new Date(minDate)
    endDate.setDate(endDate.getDate() + totalDays)

    const cursor = new Date(start)
    while (cursor <= endDate) {
      const monthStart = new Date(cursor)
      const monthEnd = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 0)

      const startDay = Math.max(
        0,
        differenceInCalendarDays(monthStart, minDate),
      )
      const endDay = Math.min(
        totalDays,
        differenceInCalendarDays(monthEnd, minDate) + 1,
      )

      if (endDay > startDay) {
        result.push({
          label: format(monthStart, "LLL yyyy", { locale: ru }),
          leftPct: (startDay / totalDays) * 100,
          widthPct: ((endDay - startDay) / totalDays) * 100,
        })
      }

      cursor.setMonth(cursor.getMonth() + 1)
      cursor.setDate(1)
    }

    return result
  }, [minDate, totalDays])

  return (
    <div className="relative h-7 border-b border-border bg-muted/50">
      {months.map((m, i) => (
        <div
          key={i}
          className="absolute top-0 h-full flex items-center px-2 text-xs text-muted-foreground font-medium border-r border-border last:border-r-0 capitalize"
          style={{ left: `${m.leftPct}%`, width: `${m.widthPct}%` }}
        >
          {m.label}
        </div>
      ))}
    </div>
  )
}
