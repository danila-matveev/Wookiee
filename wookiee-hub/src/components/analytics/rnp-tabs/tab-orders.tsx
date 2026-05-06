import { useState } from "react"
import {
  ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, Cell, ResponsiveContainer
} from "recharts"
import type { RnpWeek } from "@/types/rnp"
import { PHASE_COLORS } from "../rnp-filters"

function fmt(v: number | null, dec = 0) {
  return v === null ? "—" : v.toLocaleString("ru-RU", { maximumFractionDigits: dec })
}

function isLagged(weekEnd: string): boolean {
  const d = new Date(weekEnd)
  const now = new Date()
  return (now.getTime() - d.getTime()) / 86400000 < 21
}

interface Props { weeks: RnpWeek[] }

export function TabOrders({ weeks }: Props) {
  const [hidden, setHidden] = useState<Set<string>>(new Set())
  function toggle(key: string) {
    setHidden(prev => { const s = new Set(prev); s.has(key) ? s.delete(key) : s.add(key); return s })
  }

  return (
    <div className="space-y-4">
      <ResponsiveContainer width="100%" height={320}>
        <ComposedChart data={weeks} margin={{ top: 4, right: 48, bottom: 0, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
          <XAxis dataKey="week_label" tick={{ fontSize: 11 }} />
          <YAxis yAxisId="left" tick={{ fontSize: 11 }} />
          <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11 }} unit="%" />
          <Tooltip
            formatter={(val: unknown, name: string) => {
              if (val === null) return ["—", name]
              const n = val as number
              return [name.includes("pct") || name.includes("%") ? `${n.toFixed(1)}%` : n.toLocaleString("ru-RU"), name]
            }}
          />
          <Legend onClick={(e) => toggle(e.dataKey as string)} />

          <Bar yAxisId="left" dataKey="orders_qty" name="Заказы (шт.)" hide={hidden.has("orders_qty")}>
            {weeks.map(w => (
              <Cell
                key={w.week_start}
                fill={PHASE_COLORS[w.phase]}
                stroke={isLagged(w.week_end) ? "#888" : "none"}
                strokeDasharray={isLagged(w.week_end) ? "4 2" : "0"}
                strokeWidth={isLagged(w.week_end) ? 2 : 0}
              />
            ))}
          </Bar>
          <Line yAxisId="left" dataKey="sales_qty" name="Продажи (шт.)" stroke="#f59e0b" dot={false} hide={hidden.has("sales_qty")} />
          <Line yAxisId="right" dataKey="buyout_pct" name="Выкуп %" stroke="#8b5cf6" dot={false} strokeDasharray="5 3" hide={hidden.has("buyout_pct")} />
        </ComposedChart>
      </ResponsiveContainer>

      <div className="overflow-x-auto">
        <table className="w-full text-xs border-collapse">
          <thead>
            <tr className="border-b">
              {["Неделя", "Заказы шт", "Заказы ₽", "Продажи шт", "Продажи ₽", "Чек ₽", "СПП %", "Выкуп % ⚠"].map(h => (
                <th key={h} className="text-left py-1 px-2 font-medium text-muted-foreground">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {weeks.map(w => (
              <tr key={w.week_start} className="border-b hover:bg-muted/30">
                <td className="py-1 px-2 font-medium" style={{ color: PHASE_COLORS[w.phase] }}>{w.week_label}</td>
                <td className="py-1 px-2">{fmt(w.orders_qty)}</td>
                <td className="py-1 px-2">{fmt(w.orders_rub)}</td>
                <td className="py-1 px-2">{fmt(w.sales_qty)}</td>
                <td className="py-1 px-2">{fmt(w.sales_rub)}</td>
                <td className="py-1 px-2">{fmt(w.avg_order_rub)}</td>
                <td className="py-1 px-2">{fmt(w.spp_pct, 1)}{w.spp_pct !== null ? "%" : ""}</td>
                <td className="py-1 px-2">
                  {fmt(w.buyout_pct, 1)}{w.buyout_pct !== null ? "%" : ""}
                  {isLagged(w.week_end) && <span className="ml-1 text-amber-500">⚠</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
