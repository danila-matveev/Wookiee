import * as React from "react"
import * as Popover from "@radix-ui/react-popover"
import { Command, CommandEmpty, CommandInput, CommandItem, CommandList, CommandSeparator } from "@/components/ui/command"
import { Check, ChevronDown, Plus, X } from "lucide-react"
import { cn } from "@/lib/utils"

type Option = { value: string; label: string } | string

export interface SelectMenuProps {
  label?: string
  value: string
  options: Option[]
  onChange: (v: string) => void
  allowAdd?: boolean
  placeholder?: string
  disabled?: boolean
  emptyHint?: string                          // text shown when filter has 0 matches
  newValueLabel?: string                      // label for «+ Добавить новый»
}

export function SelectMenu({
  label, value, options, onChange,
  allowAdd, placeholder = "Выбрать…", disabled,
  emptyHint = "Ничего не найдено",
  newValueLabel = "Добавить новый",
}: SelectMenuProps) {
  const [open, setOpen] = React.useState(false)
  const [adding, setAdding] = React.useState(false)
  const [newVal, setNewVal] = React.useState("")
  const cmdWrapRef = React.useRef<HTMLDivElement>(null)
  const opts: { value: string; label: string }[] = (typeof options[0] === "string"
    ? (options as string[]).map((o) => ({ value: o, label: o }))
    : (options as { value: string; label: string }[]))
  const current = opts.find((o) => o.value === value)

  const submitNew = () => {
    const v = newVal.trim()
    if (!v) return
    onChange(v)
    setNewVal("")
    setAdding(false)
    setOpen(false)
  }

  return (
    <div>
      {label && (
        <div className="block text-[11px] uppercase tracking-wider text-muted-foreground font-medium mb-1">{label}</div>
      )}
      <Popover.Root open={open} onOpenChange={setOpen}>
        <Popover.Trigger asChild>
          <button
            type="button"
            disabled={disabled}
            aria-label={label ?? placeholder}
            aria-expanded={open}
            aria-haspopup="listbox"
            className={cn(
              "w-full flex items-center justify-between rounded-md border px-2.5 py-1.5 text-sm bg-card hover:border-foreground/20 transition-colors",
              "border-border focus:outline-none focus-visible:ring-1 focus-visible:ring-ring",
              disabled && "opacity-50 cursor-not-allowed",
            )}
          >
            <span className={current ? "text-foreground" : "text-muted-foreground"}>
              {current ? current.label : placeholder}
            </span>
            <ChevronDown className={cn("w-3.5 h-3.5 text-muted-foreground transition-transform", open && "rotate-180")} aria-hidden />
          </button>
        </Popover.Trigger>
        <Popover.Content
          className="z-50 bg-popover border border-border rounded-lg shadow-md p-0 w-[var(--radix-popover-trigger-width)]"
          sideOffset={4}
          align="start"
          onOpenAutoFocus={(e) => { e.preventDefault(); cmdWrapRef.current?.querySelector<HTMLElement>('[cmdk-root]')?.focus() }}
        >
          {!adding ? (
            <div ref={cmdWrapRef}>
              <Command>
                {opts.length > 5 && <CommandInput placeholder="Поиск…" />}
                <CommandList className="max-h-[240px]">
                  <CommandEmpty>{emptyHint}</CommandEmpty>
                  <CommandItem value="__empty__" forceMount onSelect={() => { onChange(""); setOpen(false) }}>
                    <span className="text-muted-foreground">—</span>
                  </CommandItem>
                  {opts.map((o) => (
                    <CommandItem key={o.value} value={o.label} onSelect={() => { onChange(o.value); setOpen(false) }}>
                      <span className="flex-1 truncate">{o.label}</span>
                      {o.value === value && <Check className="w-3 h-3 text-[color:var(--wk-green)]" aria-hidden />}
                    </CommandItem>
                  ))}
                  {allowAdd && (
                    <>
                      <CommandSeparator alwaysRender />
                      <CommandItem value="__add__" forceMount onSelect={() => setAdding(true)}>
                        <Plus className="w-3 h-3 mr-1.5" aria-hidden /> {newValueLabel}
                      </CommandItem>
                    </>
                  )}
                </CommandList>
              </Command>
            </div>
          ) : (
            <div className="flex items-center gap-1 p-2 border-t border-border">
              <input
                autoFocus
                value={newVal}
                onChange={(e) => setNewVal(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") submitNew()
                  if (e.key === "Escape") { setAdding(false); setNewVal("") }
                }}
                placeholder="Новое значение…"
                className="flex-1 px-2 py-1 text-xs border border-border rounded bg-card focus:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                aria-label="Ввести новое значение"
              />
              <button
                type="button"
                onClick={submitNew}
                disabled={!newVal.trim()}
                aria-label="Подтвердить"
                className="p-1 rounded text-[color:var(--wk-green)] hover:bg-muted disabled:opacity-30"
              >
                <Check className="w-3.5 h-3.5" />
              </button>
              <button
                type="button"
                onClick={() => { setAdding(false); setNewVal("") }}
                aria-label="Отмена"
                className="p-1 rounded text-muted-foreground hover:bg-muted"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          )}
        </Popover.Content>
      </Popover.Root>
    </div>
  )
}
