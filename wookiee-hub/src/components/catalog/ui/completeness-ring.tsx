interface CompletenessRingProps {
  value: number   // 0..1
  size?: number   // px, default 28
}

export function CompletenessRing({ value, size = 28 }: CompletenessRingProps) {
  const radius = (size - 4) / 2
  const circ = 2 * Math.PI * radius
  const dash = circ * Math.max(0, Math.min(1, value))
  const color =
    value >= 0.85 ? "#10B981"
    : value >= 0.6 ? "#3B82F6"
    : value >= 0.4 ? "#F59E0B"
    : "#EF4444"

  return (
    <div className="inline-flex items-center gap-2">
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          stroke="#E7E5E4" strokeWidth="2" fill="none"
        />
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          stroke={color} strokeWidth="2" fill="none"
          strokeDasharray={`${dash} ${circ}`}
          strokeLinecap="round"
        />
      </svg>
      <span className="text-xs text-stone-500 tabular-nums">{Math.round(value * 100)}%</span>
    </div>
  )
}
