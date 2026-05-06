import { useState } from "react"
import { ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts"
import type { RnpWeek } from "@/types/rnp"

function fmt(v: number | null, dec = 0) { return v === null ? "—" : v.toLocaleString("ru-RU", { maximumFractionDigits: dec }) }
interface Props { weeks: RnpWeek[] }

export function TabAdsInternal({ weeks }: Props) {
  const [hidden, setHidden] = useState<Set<string>>(new Set())
  function toggle(key: string) { setHidden(prev => { const s = new Set(prev); s.has(key) ? s.delete(key) : s.add(key); return s }) }

  return (
    <div className="space-y-4">
      <ResponsiveContainer width="100%" height={320}>
        <ComposedChart data={weeks} margin={{ top: 4, right: 48, bottom: 0, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
          <XAxis dataKey="week_label" tick={{ fontSize: 11 }} />
          <YAxis yAxisId="left" tick={{ fontSize: 11 }} />
          <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11 }} unit="%" />
          <Tooltip />
          <Legend onClick={(e) => toggle(e.dataKey as string)} />
          <Bar yAxisId="left" dataKey="adv_views" name="Показы" fill="#185FA5" opacity={0.7} hide={hidden.has("adv_views")} />
          <Bar yAxisId="left" dataKey="orders_internal_qty" name="Заказы от рекламы" fill="#1D9E75" hide={hidden.has("orders_internal_qty")} />
          <Line yAxisId="right" dataKey="ctr_internal" name="CTR %" stroke="#f59e0b" dot={false} hide={hidden.has("ctr_internal")} />
          <Line yAxisId="right" dataKey="romi_internal" name="ROMI %" stroke="#8b5cf6" dot={false} hide={hidden.has("romi_internal")} />
        </ComposedChart>
      </ResponsiveContainer>
      <div className="overflow-x-auto">
        <table className="w-full text-xs border-collapse">
          <thead><tr className="border-b">
            {["Неделя", "Расход ₽", "Показы", "Клики", "CTR %", "CPC ₽", "CPO ₽", "CPM ₽", "ROMI %"].map(h => (
              <th key={h} className="text-left py-1 px-2 font-medium text-muted-foreground">{h}</th>
            ))}
          </tr></thead>
          <tbody>{weeks.map(w => (
            <tr key={w.week_start} className="border-b hover:bg-muted/30">
              <td className="py-1 px-2 font-medium">{w.week_label}</td>
              <td className="py-1 px-2">{fmt(w.adv_internal_rub)}</td>
              <td className="py-1 px-2">{fmt(w.adv_views)}</td>
              <td className="py-1 px-2">{fmt(w.adv_clicks)}</td>
              <td className="py-1 px-2">{fmt(w.ctr_internal, 2)}{w.ctr_internal !== null ? "%" : ""}</td>
              <td className="py-1 px-2">{fmt(w.cpc_internal, 0)}</td>
              <td className="py-1 px-2">{fmt(w.cpo_internal, 0)}</td>
              <td className="py-1 px-2">{fmt(w.cpm_internal, 0)}</td>
              <td className="py-1 px-2">{fmt(w.romi_internal, 1)}{w.romi_internal !== null ? "%" : ""}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </div>
  )
}
