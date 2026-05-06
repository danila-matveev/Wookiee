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

interface Props { weeks: RnpWeek[] }

export function TabFunnel({ weeks }: Props) {
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
          <Tooltip />
          <Legend onClick={(e) => toggle(e.dataKey as string)} />
          <Bar yAxisId="left" dataKey="clicks_total" name="Клики (всего)" hide={hidden.has("clicks_total")}>
            {weeks.map(w => <Cell key={w.week_start} fill={PHASE_COLORS[w.phase]} />)}
          </Bar>
          <Bar yAxisId="left" dataKey="cart_total" name="Корзина" fill="#f59e0b" hide={hidden.has("cart_total")} />
          <Line yAxisId="right" dataKey="cr_total" name="CR клик→заказ %" stroke="#8b5cf6" dot={false} hide={hidden.has("cr_total")} />
          <Line yAxisId="right" dataKey="cr_card_to_cart" name="CR карточка→корзина %" stroke="#10b981" dot={false} hide={hidden.has("cr_card_to_cart")} />
          <Line yAxisId="right" dataKey="cr_cart_to_order" name="CR корзина→заказ %" stroke="#f43f5e" dot={false} hide={hidden.has("cr_cart_to_order")} />
        </ComposedChart>
      </ResponsiveContainer>

      <div className="overflow-x-auto">
        <table className="w-full text-xs border-collapse">
          <thead>
            <tr className="border-b">
              {["Неделя", "Клики", "Корзина", "CR клик→заказ", "CR карточка→корзина", "CR корзина→заказ"].map(h => (
                <th key={h} className="text-left py-1 px-2 font-medium text-muted-foreground">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {weeks.map(w => (
              <tr key={w.week_start} className="border-b hover:bg-muted/30">
                <td className="py-1 px-2 font-medium" style={{ color: PHASE_COLORS[w.phase] }}>{w.week_label}</td>
                <td className="py-1 px-2">{fmt(w.clicks_total)}</td>
                <td className="py-1 px-2">{fmt(w.cart_total)}</td>
                <td className="py-1 px-2">{fmt(w.cr_total, 2)}{w.cr_total !== null ? "%" : ""}</td>
                <td className="py-1 px-2">{fmt(w.cr_card_to_cart, 2)}{w.cr_card_to_cart !== null ? "%" : ""}</td>
                <td className="py-1 px-2">{fmt(w.cr_cart_to_order, 2)}{w.cr_cart_to_order !== null ? "%" : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
