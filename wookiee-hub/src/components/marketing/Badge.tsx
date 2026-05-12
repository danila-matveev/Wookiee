type BadgeColor = "green" | "blue" | "amber" | "gray"

interface BadgeProps {
  color: BadgeColor
  label: string
  compact?: boolean
}

const BG: Record<BadgeColor, string> = {
  green: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  blue: "bg-blue-50 text-blue-700 ring-blue-600/20",
  amber: "bg-amber-50 text-amber-700 ring-amber-600/20",
  gray: "bg-stone-100 text-stone-600 ring-stone-500/20",
}

const DOT: Record<BadgeColor, string> = {
  green: "bg-emerald-500",
  blue: "bg-blue-500",
  amber: "bg-amber-500",
  gray: "bg-stone-400",
}

export function Badge({ color, label, compact }: BadgeProps) {
  const bg = BG[color] ?? BG.gray
  const dot = DOT[color] ?? DOT.gray
  return (
    <span
      className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] font-medium ring-1 ring-inset ${bg}`}
    >
      {!compact && <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${dot}`} />}
      {label}
    </span>
  )
}
