import { CalendarDays, Flag, Hash, Layers, Plus, User } from "lucide-react"
import { cn } from "@/lib/utils"
import { PriorityDot } from "@/components/shared/priority-dot"
import { StatusPill } from "@/components/shared/status-pill"
import type { KanbanCard, KanbanColumn } from "@/types/kanban"

interface DrawerFieldsProps {
  card: KanbanCard
  column: KanbanColumn | undefined
}

const priorityLabel: Record<KanbanCard["priority"], string> = {
  high: "Высокий",
  medium: "Средний",
  low: "Низкий",
}

function FieldRow({
  icon,
  label,
  children,
}: {
  icon: React.ReactNode
  label: string
  children: React.ReactNode
}) {
  return (
    <div className="flex items-start gap-2">
      <div className="mt-0.5 shrink-0 text-text-dim">{icon}</div>
      <div className="min-w-0">
        <div className="text-[12px] text-text-dim">{label}</div>
        <div className="text-[13px] font-medium mt-0.5">{children}</div>
      </div>
    </div>
  )
}

export function DrawerFields({ card, column }: DrawerFieldsProps) {
  const dynamicFields = Object.entries(card.fields)

  return (
    <div className="bg-card border border-border rounded-[10px] p-4">
      <div className="grid grid-cols-2 gap-3">
        {/* Ответственный */}
        <FieldRow icon={<User size={14} />} label="Ответственный">
          {card.assignee ?? "Не назначен"}
        </FieldRow>

        {/* Дедлайн */}
        <FieldRow icon={<CalendarDays size={14} />} label="Дедлайн">
          {card.dueDate ?? "Не указан"}
        </FieldRow>

        {/* Приоритет */}
        <FieldRow icon={<Flag size={14} />} label="Приоритет">
          <span className="inline-flex items-center gap-1.5">
            <PriorityDot priority={card.priority} size={6} />
            {priorityLabel[card.priority]}
          </span>
        </FieldRow>

        {/* Статус */}
        <FieldRow icon={<Layers size={14} />} label="Статус">
          {column ? (
            <StatusPill label={column.title} color={column.color} />
          ) : (
            "—"
          )}
        </FieldRow>

        {/* Dynamic fields */}
        {dynamicFields.map(([key, value]) => (
          <FieldRow key={key} icon={<Hash size={14} />} label={key}>
            {value}
          </FieldRow>
        ))}
      </div>

      {/* Add field button */}
      <button
        type="button"
        className={cn(
          "w-full border border-dashed border-border rounded-lg p-2",
          "flex items-center justify-center gap-1.5",
          "text-[12px] text-text-dim",
          "hover:border-accent-border hover:text-accent",
          "transition-colors cursor-pointer mt-3"
        )}
      >
        <Plus size={12} />
        Добавить поле
      </button>
    </div>
  )
}
