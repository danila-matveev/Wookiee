import { Badge } from "./badge"

type Variant = "emerald" | "blue" | "amber" | "red" | "purple" | "teal" | "gray"

type Status =
  | "active" | "draft" | "review" | "archived"
  | "pending" | "approved" | "rejected"
  | "in_progress" | "completed" | "blocked"

const STATUS_MAP: Record<Status, { label: string; variant: Variant; dot: boolean }> = {
  active:      { label: "Активен",     variant: "emerald", dot: true },
  draft:       { label: "Черновик",    variant: "gray",    dot: false },
  review:      { label: "На ревью",    variant: "amber",   dot: true },
  archived:    { label: "Архив",       variant: "gray",    dot: false },
  pending:     { label: "Ожидание",    variant: "amber",   dot: true },
  approved:    { label: "Одобрено",    variant: "emerald", dot: false },
  rejected:    { label: "Отклонено",   variant: "red",     dot: false },
  in_progress: { label: "В работе",    variant: "blue",    dot: true },
  completed:   { label: "Завершено",   variant: "emerald", dot: false },
  blocked:     { label: "Блокировка",  variant: "red",     dot: true },
}

export interface StatusBadgeProps {
  status: Status
  className?: string
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const entry = STATUS_MAP[status]
  return (
    <Badge variant={entry.variant} dot={entry.dot} className={className}>
      {entry.label}
    </Badge>
  )
}
