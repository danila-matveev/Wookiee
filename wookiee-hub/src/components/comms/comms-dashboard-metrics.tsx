import { motion, useReducedMotion } from "motion/react"
import { cn } from "@/lib/utils"
import { staggerContainer, staggerItem } from "@/lib/motion"
import { formatNumber, formatPercent } from "@/lib/format"
import type { CommsDashboardMetrics as Metrics } from "@/types/comms"

interface CommsDashboardMetricsProps {
  metrics: Metrics
  className?: string
}

interface SimpleMetric {
  label: string
  value: string
  sub: string
}

export function CommsDashboardMetrics({ metrics, className }: CommsDashboardMetricsProps) {
  const reducedMotion = useReducedMotion()

  const cards: SimpleMetric[] = [
    {
      label: "Поступило",
      value: formatNumber(metrics.totalReceived),
      sub: "отзывов и вопросов",
    },
    {
      label: "Ожидают публикации",
      value: formatNumber(metrics.awaitingPublish),
      sub: "готовых ответов",
    },
    {
      label: "Неотвеченные",
      value: `${formatNumber(metrics.unanswered)} (${formatPercent(metrics.unansweredPercent)})`,
      sub: "требуют внимания",
    },
    {
      label: "Ср. рейтинг",
      value: metrics.avgRating.toFixed(1),
      sub: `${formatPercent(metrics.positivePercent)} положительных`,
    },
  ]

  return (
    <motion.div
      className={cn("grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3", className)}
      variants={reducedMotion ? undefined : staggerContainer}
      initial={reducedMotion ? false : "hidden"}
      animate="visible"
    >
      {cards.map((card) => (
        <motion.div
          key={card.label}
          variants={reducedMotion ? undefined : staggerItem}
          className="bg-card border border-border rounded-[10px] p-4 transition-all duration-150 hover:border-accent-border hover:shadow-glow"
        >
          <div className="text-[11px] uppercase tracking-[0.04em] text-muted-foreground font-semibold mb-2">
            {card.label}
          </div>
          <div className="text-[22px] font-bold leading-tight tabular-nums mb-1">{card.value}</div>
          <div className="text-[12px] text-muted-foreground">{card.sub}</div>
        </motion.div>
      ))}
    </motion.div>
  )
}
