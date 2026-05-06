import { useState } from "react"
import { ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts"
import type { RnpWeek } from "@/types/rnp"

function fmt(v: number | null, dec = 0) { return v === null ? "—" : v.toLocaleString("ru-RU", { maximumFractionDigits: dec }) }
interface Props { weeks: RnpWeek[] }

export function TabAdsExternal({ weeks }: Props) {
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
          <Bar yAxisId="left" dataKey="blogger_rub" name="Блогеры ₽" stackId="ext" fill="#185FA5" hide={hidden.has("blogger_rub")} />
          <Bar yAxisId="left" dataKey="vk_sids_rub" name="ВК SIDS ₽" stackId="ext" fill="#1D9E75" hide={hidden.has("vk_sids_rub")} />
          <Bar yAxisId="left" dataKey="sids_contractor_rub" name="SIDS Contractor ₽" stackId="ext" fill="#f59e0b" hide={hidden.has("sids_contractor_rub")} />
          <Bar yAxisId="left" dataKey="yandex_contractor_rub" name="Яндекс ₽" stackId="ext" fill="#8b5cf6" hide={hidden.has("yandex_contractor_rub")} />
          <Line yAxisId="right" dataKey="ctr_external" name="CTR внешн. %" stroke="#E24B4A" dot={false} hide={hidden.has("ctr_external")} />
        </ComposedChart>
      </ResponsiveContainer>
      <div className="overflow-x-auto">
        <table className="w-full text-xs border-collapse">
          <thead><tr className="border-b">
            {["Неделя", "Блогеры ₽", "ROMI %", "Просм.", "Клики", "ВК SIDS ₽", "CPO ₽", "SIDS C. ₽", "Яндекс ₽"].map(h => (
              <th key={h} className="text-left py-1 px-2 font-medium text-muted-foreground">{h}</th>
            ))}
          </tr></thead>
          <tbody>{weeks.map(w => (
            <tr key={w.week_start} className="border-b hover:bg-muted/30">
              <td className="py-1 px-2 font-medium">{w.week_label}</td>
              <td className="py-1 px-2">{fmt(w.blogger_rub)}{w.blogger_no_stats ? " ⚠" : ""}</td>
              <td className="py-1 px-2">{fmt(w.romi_blogger, 1)}{w.romi_blogger !== null ? "%" : ""}</td>
              <td className="py-1 px-2">{fmt(w.blogger_views)}</td>
              <td className="py-1 px-2">{fmt(w.blogger_clicks)}</td>
              <td className="py-1 px-2">{fmt(w.vk_sids_rub)}</td>
              <td className="py-1 px-2">{fmt(w.cpo_vk_sids, 0)}</td>
              <td className="py-1 px-2">{fmt(w.sids_contractor_rub)}</td>
              <td className="py-1 px-2">{fmt(w.yandex_contractor_rub)}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </div>
  )
}
