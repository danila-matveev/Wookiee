import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  ResponsiveContainer,
  Cell,
  LabelList,
} from "recharts"
import { cn } from "@/lib/utils"
import { commsRatingDistribution } from "@/data/community-mock"

const ratingColors: Record<number, string> = {
  5: "#22c55e",
  4: "#86efac",
  3: "#facc15",
  2: "#fb923c",
  1: "#ef4444",
}

const chartData = commsRatingDistribution.map((d) => ({
  label: `★${d.rating}`,
  count: d.count,
  rating: d.rating,
}))

export function AnalyticsRatingChart({ className }: { className?: string }) {
  return (
    <div className={cn("bg-card border border-border rounded-[10px] p-4", className)}>
      <h3 className="text-sm font-semibold mb-4">Распределение рейтинга</h3>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={chartData} layout="vertical" margin={{ left: 8, right: 40 }}>
          <XAxis type="number" hide />
          <YAxis
            type="category"
            dataKey="label"
            tick={{ fontSize: 13, fill: "var(--foreground)", fontWeight: 600 }}
            axisLine={false}
            tickLine={false}
            width={36}
          />
          <Bar dataKey="count" radius={[0, 4, 4, 0]} barSize={20}>
            {chartData.map((entry) => (
              <Cell key={entry.label} fill={ratingColors[entry.rating]} />
            ))}
            <LabelList
              dataKey="count"
              position="right"
              style={{ fontSize: 12, fill: "var(--muted-foreground)", fontVariantNumeric: "tabular-nums" }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
