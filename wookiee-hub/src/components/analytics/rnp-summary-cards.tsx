import type { RnpWeek } from "@/types/rnp"
import { PHASE_COLORS } from "./rnp-filters"

function fmt(n: number | null, decimals = 0): string {
  if (n === null || n === undefined) return "—"
  return n.toLocaleString("ru-RU", { maximumFractionDigits: decimals })
}

function sumField(weeks: RnpWeek[], field: keyof RnpWeek): number {
  return weeks.reduce((acc, w) => acc + ((w[field] as number) ?? 0), 0)
}

interface CardProps {
  label: string
  value: string
  sub?: string
  accent?: string
}

function Card({ label, value, sub, accent }: CardProps) {
  return (
    <div className="rounded-lg border bg-card p-4 flex flex-col gap-1">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-2xl font-bold" style={accent ? { color: accent } : {}}>
        {value}
      </span>
      {sub && <span className="text-xs text-muted-foreground">{sub}</span>}
    </div>
  )
}

interface RnpSummaryCardsProps {
  weeks: RnpWeek[]
}

export function RnpSummaryCards({ weeks }: RnpSummaryCardsProps) {
  if (!weeks.length) return null

  const ordersQty  = sumField(weeks, "orders_qty")
  const ordersRub  = sumField(weeks, "orders_rub")
  const salesQty   = sumField(weeks, "sales_qty")
  const salesRub   = sumField(weeks, "sales_rub")

  const mbaRub = sumField(weeks, "margin_before_ads_rub")
  const mbaPct = salesRub > 0 ? (mbaRub / salesRub) * 100 : null

  const mRub  = sumField(weeks, "margin_rub")
  const mPct  = salesRub > 0 ? (mRub / salesRub) * 100 : null
  const mPhase = mPct !== null
    ? mPct >= 15 ? "norm" : mPct < 10 ? "decline" : "recovery"
    : "recovery"

  const advTotal  = sumField(weeks, "adv_total_rub")
  const drrPct    = ordersRub > 0 ? (advTotal / ordersRub) * 100 : null

  const mfRub = sumField(weeks, "margin_forecast_rub")
  const sfRub = sumField(weeks, "sales_forecast_rub")
  const mfPct = sfRub > 0 ? (mfRub / sfRub) * 100 : null

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
      <Card
        label="Заказы"
        value={fmt(ordersQty)}
        sub={`${fmt(ordersRub / 1000)} тыс. ₽`}
      />
      <Card
        label="Продажи"
        value={fmt(salesQty)}
        sub={`${fmt(salesRub / 1000)} тыс. ₽`}
      />
      <Card
        label="Маржа до рекламы"
        value={mbaPct !== null ? `${fmt(mbaPct, 1)}%` : "—"}
        sub={`${fmt(mbaRub / 1000)} тыс. ₽`}
        accent="#185FA5"
      />
      <Card
        label="Маржа после рекламы"
        value={mPct !== null ? `${fmt(mPct, 1)}%` : "—"}
        sub={`${fmt(mRub / 1000)} тыс. ₽`}
        accent={PHASE_COLORS[mPhase]}
      />
      <Card
        label="ДРР итого (от заказов)"
        value={drrPct !== null ? `${fmt(drrPct, 1)}%` : "—"}
        accent={drrPct !== null && drrPct > 25 ? "#E24B4A" : undefined}
      />
      <Card
        label="Прогноз маржи"
        value={mfPct !== null ? `${fmt(mfPct, 1)}%` : "—"}
        sub={`${fmt(mfRub / 1000)} тыс. ₽`}
      />
    </div>
  )
}
