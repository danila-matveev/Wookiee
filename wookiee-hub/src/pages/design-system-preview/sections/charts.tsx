import { TrendingUp } from "lucide-react"
import { EmptyState } from "@/components/ui-v2/feedback"
import { Demo, SubSection } from "../shared"

/**
 * ChartsSection — placeholder for Wave 3b deps.
 *
 * Canonical reference: `foundation.jsx:1640-1946` (`function ChartsSection()`).
 * That section requires the `chartTokens` palette hook + a set of Recharts
 * wrappers (multi-series line, stacked bar, donut, gauge, funnel, calendar
 * heatmap, sparkline KPI). None of those primitives have been ported yet —
 * they land in **Wave 3b — Charts deps**.
 */
export function ChartsSection() {
  return (
    <div className="space-y-12">
      <SubSection
        title="Charts"
        description="Раздел появится после Wave 3b — Recharts-обёртки ещё не созданы."
      >
        <Demo title="Coming soon" full padded={false}>
          <EmptyState
            icon={<TrendingUp className="w-10 h-10" />}
            title="Charts — coming in Wave 3b"
            description="Канонический раздел `foundation.jsx:1640-1946` собран на Recharts с собственной палитрой `chartTokens` (foundation.jsx:38-75) и набором wrappers. После Wave 3b здесь появится демонстрация всех 12 типов графиков."
            action={
              <div className="text-left text-xs text-muted space-y-1 max-w-sm mx-auto mt-2">
                <div className="text-[10px] uppercase tracking-wider text-label mb-2">
                  Ожидается в Wave 3b
                </div>
                <div>· Multi-series Line · P&L разрез (5 серий)</div>
                <div>· Stacked Bar · структура расходов (6 каналов)</div>
                <div>· Combo · Bar + Line с двумя осями</div>
                <div>· Базовая Line / Area / Bar / Stacked Area</div>
                <div>· Doughnut · Gauge · Funnel</div>
                <div>· Calendar Heatmap · контент-завод</div>
                <div>· Sparkline KPI cards + inline в таблицах</div>
              </div>
            }
          />
        </Demo>
      </SubSection>
    </div>
  )
}
