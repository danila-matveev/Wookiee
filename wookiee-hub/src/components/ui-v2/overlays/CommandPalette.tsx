import * as React from "react"
import { createPortal } from "react-dom"
import { Search, ArrowRight } from "lucide-react"
import { cn } from "@/lib/utils"

export interface CommandPaletteCommand {
  id: string
  label: string
  description?: string
  icon?: React.ComponentType<{ className?: string }>
  shortcut?: string
  /** Group section header — rendered as separator (our extension). */
  group?: string
  /**
   * UPPERCASE per-item tag rendered in a leading `w-16` column.
   * Canonical (foundation.jsx:2358) — `<span className="text-[10px]
   * uppercase tracking-wider w-16 text-label">{type}</span>`. Use for
   * type markers like «МОДЕЛЬ», «ЦВЕТ», «СТРАНИЦА».
   */
  itemType?: string
  keywords?: string[]
  onSelect: () => void
}

export interface CommandPaletteProps {
  open: boolean
  onClose: () => void
  commands: CommandPaletteCommand[]
  placeholder?: string
  emptyMessage?: string
  className?: string
}

interface GroupedCommands {
  group: string | undefined
  items: CommandPaletteCommand[]
}

function groupCommands(commands: CommandPaletteCommand[]): GroupedCommands[] {
  const groups = new Map<string | undefined, CommandPaletteCommand[]>()
  for (const cmd of commands) {
    const key = cmd.group
    const list = groups.get(key)
    if (list) {
      list.push(cmd)
    } else {
      groups.set(key, [cmd])
    }
  }
  return Array.from(groups.entries()).map(([group, items]) => ({ group, items }))
}

function matchCommand(cmd: CommandPaletteCommand, query: string): boolean {
  if (!query) return true
  const q = query.trim().toLowerCase()
  if (!q) return true
  const haystack = [cmd.label, cmd.description, cmd.group, ...(cmd.keywords ?? [])]
    .filter(Boolean)
    .join(" ")
    .toLowerCase()
  return haystack.includes(q)
}

export function CommandPalette({
  open,
  onClose,
  commands,
  placeholder = "Поиск команд…",
  emptyMessage = "Ничего не найдено",
  className,
}: CommandPaletteProps) {
  const [query, setQuery] = React.useState("")
  const [activeIndex, setActiveIndex] = React.useState(0)
  const inputRef = React.useRef<HTMLInputElement | null>(null)
  const itemRefs = React.useRef<Array<HTMLButtonElement | null>>([])

  // Reset when (re)opening.
  React.useEffect(() => {
    if (open) {
      setQuery("")
      setActiveIndex(0)
      window.requestAnimationFrame(() => inputRef.current?.focus())
    }
  }, [open])

  const filtered = React.useMemo(
    () => commands.filter((cmd) => matchCommand(cmd, query)),
    [commands, query],
  )

  // Reset active index when filter changes.
  React.useEffect(() => {
    setActiveIndex(0)
  }, [query, commands])

  // Scroll active item into view.
  React.useEffect(() => {
    const node = itemRefs.current[activeIndex]
    node?.scrollIntoView({ block: "nearest" })
  }, [activeIndex])

  React.useEffect(() => {
    if (!open) return
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation()
        onClose()
      }
    }
    document.addEventListener("keydown", handleKey)
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = "hidden"
    return () => {
      document.removeEventListener("keydown", handleKey)
      document.body.style.overflow = prevOverflow
    }
  }, [open, onClose])

  if (!open) return null

  const groups = groupCommands(filtered)

  // Build a flat ordered list to align with arrow navigation.
  const flatOrder: CommandPaletteCommand[] = groups.flatMap((g) => g.items)

  const handleKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault()
      setActiveIndex((idx) => (flatOrder.length === 0 ? 0 : (idx + 1) % flatOrder.length))
    } else if (event.key === "ArrowUp") {
      event.preventDefault()
      setActiveIndex((idx) =>
        flatOrder.length === 0 ? 0 : (idx - 1 + flatOrder.length) % flatOrder.length,
      )
    } else if (event.key === "Enter") {
      event.preventDefault()
      const cmd = flatOrder[activeIndex]
      if (cmd) {
        cmd.onSelect()
        onClose()
      }
    }
  }

  const node = (
    <div
      // Canonical (foundation.jsx:2345) — warm stone-900 tint in light mode, black in dark.
      className="fixed inset-0 flex items-start justify-center pt-[12vh] px-4 bg-stone-900/40 dark:bg-black/60 backdrop-blur-sm"
      style={{ zIndex: "var(--z-modal)" }}
      role="dialog"
      aria-modal="true"
      aria-label="Командная палитра"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <div
        className={cn(
          "w-full max-w-xl bg-surface rounded-lg border border-default overflow-hidden",
          "shadow-[var(--shadow-lg)]",
          className,
        )}
        onMouseDown={(event) => event.stopPropagation()}
        onKeyDown={handleKeyDown}
      >
        <div className="flex items-center gap-2 px-3.5 py-3 border-b border-default">
          <Search className="w-4 h-4 text-muted" aria-hidden />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={placeholder}
            className="flex-1 bg-transparent outline-none text-sm text-primary placeholder:text-[color:var(--color-text-label)]"
          />
          <span className="text-[10px] uppercase tracking-wider text-muted font-mono px-1.5 py-0.5 rounded border border-default">
            esc
          </span>
        </div>
        <div className="max-h-96 overflow-y-auto py-1">
          {flatOrder.length === 0 ? (
            <div className="px-3.5 py-8 text-center text-xs text-muted italic">
              {emptyMessage}
            </div>
          ) : (
            (() => {
              let flatIndex = -1
              return groups.map((group) => (
                <div key={group.group ?? "_default"} className="py-1">
                  {group.group && (
                    <div className="px-3.5 py-1 text-[10px] uppercase tracking-wider text-[color:var(--color-text-label)]">
                      {group.group}
                    </div>
                  )}
                  {group.items.map((cmd) => {
                    flatIndex += 1
                    const itemIndex = flatIndex
                    const isActive = itemIndex === activeIndex
                    const Icon = cmd.icon
                    return (
                      <button
                        key={cmd.id}
                        type="button"
                        ref={(el) => {
                          itemRefs.current[itemIndex] = el
                        }}
                        onMouseEnter={() => setActiveIndex(itemIndex)}
                        onClick={() => {
                          cmd.onSelect()
                          onClose()
                        }}
                        className={cn(
                          "w-full px-3.5 py-2 flex items-center gap-3 text-left outline-none",
                          isActive ? "bg-surface-muted" : "hover:bg-surface-muted",
                        )}
                      >
                        {cmd.itemType ? (
                          <span className="text-[10px] uppercase tracking-wider text-label w-16 shrink-0">
                            {cmd.itemType}
                          </span>
                        ) : Icon ? (
                          <Icon className="w-3.5 h-3.5 text-muted shrink-0" />
                        ) : (
                          <span className="w-3.5 h-3.5 shrink-0" />
                        )}
                        <div className="flex-1 min-w-0">
                          <div className="text-sm text-primary truncate">{cmd.label}</div>
                          {cmd.description && (
                            <div className="text-xs text-muted truncate">{cmd.description}</div>
                          )}
                        </div>
                        {cmd.shortcut && (
                          <span className="text-[10px] uppercase tracking-wider text-muted font-mono px-1.5 py-0.5 rounded border border-default">
                            {cmd.shortcut}
                          </span>
                        )}
                        <ArrowRight className="w-3.5 h-3.5 text-[color:var(--color-text-label)] shrink-0" />
                      </button>
                    )
                  })}
                </div>
              ))
            })()
          )}
        </div>
      </div>
    </div>
  )

  return createPortal(node, document.body)
}
