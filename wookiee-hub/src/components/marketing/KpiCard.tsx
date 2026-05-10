// wookiee-hub/src/components/marketing/KpiCard.tsx
export interface KpiCardProps {
  label: string
  value: string
  sub?: string
}

export function KpiCard({ label, value, sub }: KpiCardProps) {
  return (
    <div className="bg-card rounded-lg border border-border px-4 py-3">
      <div className="text-[11px] uppercase tracking-wider text-muted-foreground font-medium">{label}</div>
      <div className="text-xl font-medium text-foreground tabular-nums leading-tight mt-0.5">{value}</div>
      {sub && <div className="text-[10px] text-muted-foreground mt-0.5">{sub}</div>}
    </div>
  )
}
