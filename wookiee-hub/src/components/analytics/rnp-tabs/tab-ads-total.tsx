import { useState } from "react"
import { ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts"
import type { RnpWeek } from "@/types/rnp"

function fmt(v: number | null, dec = 0) { return v === null ? "—" : v.toLocaleString("ru-RU", { maximumFractionDigits: dec }) }
interface Props { weeks: RnpWeek[] }

export function TabAdsTotal({ weeks }: Props) {
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
          <Bar yAxisId="left" dataKey="adv_internal_rub" name="Внутренняя реклама ₽" stackId="adv" fill="#185FA5" hide={hidden.has("adv_internal_rub")} />
          <Bar yAxisId="left" dataKey="adv_external_rub" name="Внешняя реклама ₽" stackId="adv" fill="#f59e0b" hide={hidden.has("adv_external_rub")} />
          <Line yAxisId="right" dataKey="drr_total_from_orders" name="ДРР итого (от заказов) %" stroke="#E24B4A" dot={false} hide={hidden.has("drr_total_from_orders")} />
          <Line yAxisId="right" dataKey="drr_internal_from_orders" name="ДРР внутр. %" stroke="#8b5cf6" dot={false} strokeDasharray="4 2" hide={hidden.has("drr_internal_from_orders")} />
        </ComposedChart>
      </ResponsiveContainer>
      <div className="overflow-x-auto">
        <table className="w-full text-xs border-collapse">
          <thead><tr className="border-b">
            {["Неделя", "Реклама итого ₽", "Внутр. ₽", "Внешн. ₽", "ДРР итого %", "ДРР внутр. %", "ДРР внешн. %"].map(h => (
              <th key={h} className="text-left py-1 px-2 font-medium text-muted-foreground">{h}</th>
            ))}
          </tr></thead>
          <tbody>{weeks.map(w => (
            <tr key={w.week_start} className="border-b hover:bg-muted/30">
              <td className="py-1 px-2 font-medium">{w.week_label}</td>
              <td className="py-1 px-2">{fmt(w.adv_total_rub)}</td>
              <td className="py-1 px-2">{fmt(w.adv_internal_rub)}</td>
              <td className="py-1 px-2">{fmt(w.adv_external_rub)}</td>
              <td className="py-1 px-2">{fmt(w.drr_total_from_orders, 1)}{w.drr_total_from_orders !== null ? "%" : ""}</td>
              <td className="py-1 px-2">{fmt(w.drr_internal_from_orders, 1)}{w.drr_internal_from_orders !== null ? "%" : ""}</td>
              <td className="py-1 px-2">{fmt(w.drr_external_from_orders, 1)}{w.drr_external_from_orders !== null ? "%" : ""}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </div>
  )
}
