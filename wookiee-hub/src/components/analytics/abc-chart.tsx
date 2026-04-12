import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts"
import { formatPercent, formatCurrency } from "@/lib/format"

const CATEGORY_COLORS: Record<string, string> = {
  A: "#34d399",   // green
  B: "#fbbf24",   // amber
  C: "#f87171",   // red
  New: "#60a5fa", // blue
}

const CATEGORY_LABELS: Record<string, string> = {
  A: "Группа A",
  B: "Группа B",
  C: "Группа C",
  New: "Новинки",
}

interface AbcChartEntry {
  group: string
  revenue: number
  share: number
}

interface AbcChartProps {
  data: AbcChartEntry[]
}

export function AbcChart({ data }: AbcChartProps) {
  // Filter out categories with 0 share
  const chartData = data.filter((d) => d.share > 0)

  return (
    <div className="bg-card border border-border rounded-[10px] p-4">
      <h3 className="text-sm font-semibold mb-4">Распределение выручки</h3>
      <ResponsiveContainer width="100%" height={180}>
        <PieChart>
          <Pie
            data={chartData}
            dataKey="share"
            nameKey="group"
            innerRadius={50}
            outerRadius={80}
            paddingAngle={2}
          >
            {chartData.map((entry) => (
              <Cell key={entry.group} fill={CATEGORY_COLORS[entry.group] ?? "#888"} />
            ))}
          </Pie>
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload?.[0]) return null
              const d = payload[0].payload as AbcChartEntry
              return (
                <div className="bg-card border border-border rounded-md px-3 py-2 shadow-lg text-[12px]">
                  <div className="font-semibold">{CATEGORY_LABELS[d.group] ?? d.group}</div>
                  <div className="text-muted-foreground">{formatPercent(d.share)} доля</div>
                  <div className="text-muted-foreground">{formatCurrency(d.revenue)}</div>
                </div>
              )
            }}
          />
        </PieChart>
      </ResponsiveContainer>
      <div className="flex flex-col gap-2 mt-4">
        {data.map((entry) => (
          <div key={entry.group} className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span
                className="w-2.5 h-2.5 rounded-sm"
                style={{ backgroundColor: CATEGORY_COLORS[entry.group] ?? "#888" }}
              />
              <span className="text-[12px] text-muted-foreground">
                {CATEGORY_LABELS[entry.group] ?? entry.group}
              </span>
            </div>
            <span className="text-[12px] font-semibold">
              {entry.share}%
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
