import { cn } from "@/lib/utils"

interface StatusPillProps {
  label: string
  color: string
  className?: string
}

export function StatusPill({ label, color, className }: StatusPillProps) {
  return (
    <span
      className={cn("inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold", className)}
      style={{ backgroundColor: `color-mix(in oklch, ${color} 20%, transparent)`, color }}
    >
      {label}
    </span>
  )
}
