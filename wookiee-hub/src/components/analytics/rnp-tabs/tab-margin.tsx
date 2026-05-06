import { useState } from "react"
import { ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, Cell, ResponsiveContainer } from "recharts"
import type { RnpWeek } from "@/types/rnp"
import { PHASE_COLORS } from "../rnp-filters"

function fmt(v: number | null, dec = 0) { return v === null ? "—" : v.toLocaleString("ru-RU", { maximumFractionDigits: dec }) }
interface Props { weeks: RnpWeek[] }

export function TabMargin({ weeks }: Props) {
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
          <Bar yAxisId="left" dataKey="margin_before_ads_rub" name="Маржа до рекламы ₽" fill="#94a3b8" opacity={0.5} hide={hidden.has("margin_before_ads_rub")} />
          <Bar yAxisId="left" dataKey="margin_rub" name="Маржа после рекламы ₽" hide={hidden.has("margin_rub")}>
            {weeks.map(w => <Cell key={w.week_start} fill={PHASE_COLORS[w.phase]} />)}
          </Bar>
          <Line yAxisId="right" dataKey="margin_before_ads_pct" name="Маржа до рекл. %" stroke="#185FA5" dot={false} strokeDasharray="5 3" hide={hidden.has("margin_before_ads_pct")} />
          <Line yAxisId="right" dataKey="margin_pct" name="Маржа после рекл. %" stroke="#1D9E75" dot={false} hide={hidden.has("margin_pct")} />
          <Line yAxisId="right" dataKey="margin_forecast_pct" name="Прогноз маржи %" stroke="#f59e0b" dot={false} strokeDasharray="3 3" hide={hidden.has("margin_forecast_pct")} />
        </ComposedChart>
      </ResponsiveContainer>
      <div className="overflow-x-auto">
        <table className="w-full text-xs border-collapse">
          <thead><tr className="border-b">
            {["Неделя", "Маржа до рекл. ₽", "До рекл. %", "Маржа после рекл. ₽", "После рекл. %", "Прогноз ₽", "Прогноз %"].map(h => (
              <th key={h} className="text-left py-1 px-2 font-medium text-muted-foreground">{h}</th>
            ))}
          </tr></thead>
          <tbody>{weeks.map(w => (
            <tr key={w.week_start} className="border-b hover:bg-muted/30">
              <td className="py-1 px-2 font-medium" style={{ color: PHASE_COLORS[w.phase] }}>{w.week_label}</td>
              <td className="py-1 px-2">{fmt(w.margin_before_ads_rub)}</td>
              <td className="py-1 px-2 text-[#185FA5] font-medium">{fmt(w.margin_before_ads_pct, 1)}{w.margin_before_ads_pct !== null ? "%" : ""}</td>
              <td className="py-1 px-2">{fmt(w.margin_rub)}</td>
              <td className="py-1 px-2 font-medium" style={{ color: PHASE_COLORS[w.phase] }}>{fmt(w.margin_pct, 1)}{w.margin_pct !== null ? "%" : ""}</td>
              <td className="py-1 px-2">{fmt(w.margin_forecast_rub)}</td>
              <td className="py-1 px-2">{fmt(w.margin_forecast_pct, 1)}{w.margin_forecast_pct !== null ? "%" : ""}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </div>
  )
}
