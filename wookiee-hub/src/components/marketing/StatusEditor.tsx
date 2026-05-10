import * as DropdownMenu from "@radix-ui/react-dropdown-menu"
import { Check, ChevronDown } from "lucide-react"
import { Badge } from "@/components/crm/ui/Badge"

const STATUSES = {
  active:  { label: "Используется", tone: "success"   as const },
  free:    { label: "Свободен",     tone: "info"       as const },
  archive: { label: "Архив",        tone: "secondary"  as const },
}
type Status = keyof typeof STATUSES

export function StatusEditor({ status, onChange, disabled }: { status: Status; onChange: (s: Status) => void; disabled?: boolean }) {
  const cur = STATUSES[status]
  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild disabled={disabled}>
        <button
          type="button"
          aria-label={`Текущий статус: ${cur.label}. Нажмите чтобы изменить.`}
          className="group flex items-center gap-1.5 px-2 py-1 rounded-md border border-transparent hover:border-border transition-colors disabled:opacity-50"
        >
          <Badge tone={cur.tone}>{cur.label}</Badge>
          <ChevronDown className="w-3 h-3 text-muted-foreground/50 group-hover:text-muted-foreground" aria-hidden />
        </button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Content className="z-50 bg-popover border border-border rounded-lg shadow-md py-1 min-w-[150px]">
        {(Object.keys(STATUSES) as Status[]).map((k) => {
          const s = STATUSES[k]
          return (
            <DropdownMenu.Item key={k}
              onSelect={() => onChange(k)}
              className="flex items-center gap-2 px-3 py-1.5 text-sm hover:bg-muted cursor-pointer outline-none data-[highlighted]:bg-muted"
            >
              <Badge tone={s.tone}>{s.label}</Badge>
              {k === status && <Check className="w-3 h-3 text-[color:var(--wk-green)] ml-auto" aria-hidden />}
            </DropdownMenu.Item>
          )
        })}
      </DropdownMenu.Content>
    </DropdownMenu.Root>
  )
}
