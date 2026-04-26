import { motion, useReducedMotion } from "motion/react"
import { MetricCard } from "@/components/shared/metric-card"
import { staggerContainer, staggerItem } from "@/lib/motion"
import { cn } from "@/lib/utils"
import { commsAnalyticsMetrics } from "@/data/community-mock"

function formatMinutesLabel(minutes: number): string {
  if (minutes < 60) return `${minutes}м`
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  if (m === 0) return `${h}ч`
  return `${h}ч ${m.toString().padStart(2, "0")}м`
}

export function CommsAnalyticsMetrics({ className }: { className?: string }) {
  const reducedMotion = useReducedMotion()

  const metrics = [
    {
      label: "Ср. время ответа (отзывы)",
      value: formatMinutesLabel(commsAnalyticsMetrics.avgResponseTimeReviews),
      sub: "среднее за период",
    },
    {
      label: "Ср. время ответа (вопросы)",
      value: formatMinutesLabel(commsAnalyticsMetrics.avgResponseTimeQuestions),
      sub: "среднее за период",
    },
    {
      label: "Отвечено",
      value: `${commsAnalyticsMetrics.responseRate}%`,
      sub: `${commsAnalyticsMetrics.totalReviews} всего отзывов`,
    },
    {
      label: "Средний рейтинг",
      value: commsAnalyticsMetrics.avgRating.toFixed(1),
      sub: "по всем магазинам",
    },
  ]

  return (
    <motion.div
      className={cn("grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3", className)}
      variants={reducedMotion ? undefined : staggerContainer}
      initial={reducedMotion ? false : "hidden"}
      animate="visible"
    >
      {metrics.map((m) => (
        <motion.div key={m.label} variants={reducedMotion ? undefined : staggerItem}>
          <MetricCard {...m} />
        </motion.div>
      ))}
    </motion.div>
  )
}
