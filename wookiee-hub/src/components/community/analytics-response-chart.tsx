import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
} from "recharts"
import { cn } from "@/lib/utils"
import { commsResponseTimeData } from "@/data/community-mock"

function formatMinutes(value: number): string {
  if (value < 60) return `${Math.round(value)}м`
  const hours = Math.floor(value / 60)
  const mins = Math.round(value % 60)
  if (mins === 0) return `${hours}ч`
  return `${hours}ч ${mins}м`
}

export function AnalyticsResponseChart({ className }: { className?: string }) {
  return (
    <div className={cn("bg-card border border-border rounded-[10px] p-4", className)}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold">Среднее время ответа по дням</h3>
        <div className="flex gap-3 text-[11px] text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-accent" />
            Отзывы
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-wk-blue" />
            Вопросы
          </span>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={commsResponseTimeData}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 11, fill: "var(--text-dim)", style: { fontVariantNumeric: "tabular-nums" } }}
            axisLine={{ stroke: "var(--border)" }}
            tickLine={false}
          />
          <YAxis
            tickFormatter={formatMinutes}
            tick={{ fontSize: 11, fill: "var(--text-dim)", style: { fontVariantNumeric: "tabular-nums" } }}
            axisLine={false}
            tickLine={false}
            allowDecimals={false}
          />
          <Tooltip
            formatter={(value: number, name: string) => [formatMinutes(value), name]}
            contentStyle={{
              backgroundColor: "var(--card)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              fontSize: 12,
            }}
            labelStyle={{ color: "var(--muted-foreground)", fontSize: 11 }}
          />
          <Line
            type="monotone"
            dataKey="avgMinutesReviews"
            stroke="var(--accent)"
            strokeWidth={2}
            dot={false}
            name="Отзывы"
          />
          <Line
            type="monotone"
            dataKey="avgMinutesQuestions"
            stroke="var(--wk-blue)"
            strokeWidth={2}
            dot={false}
            name="Вопросы"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
