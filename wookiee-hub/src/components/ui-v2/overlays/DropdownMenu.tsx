import * as React from "react"
import { Popover } from "./Popover"
import type { PopoverPlacement } from "./Popover"
import { cn } from "@/lib/utils"

export interface DropdownMenuItem {
  /** Stable id. Optional — fallback to label. */
  id?: string
  label: string
  icon?: React.ComponentType<{ className?: string }>
  shortcut?: string
  danger?: boolean
  disabled?: boolean
  onClick?: () => void
  /** Render as separator instead of clickable item. */
  divider?: boolean
}

export interface DropdownMenuProps {
  trigger: React.ReactNode
  items: DropdownMenuItem[]
  placement?: PopoverPlacement
  className?: string
  /** Min width of menu panel. Default w-56. */
  menuClassName?: string
}

export function DropdownMenu({
  trigger,
  items,
  placement = "bottom",
  className,
  menuClassName,
}: DropdownMenuProps) {
  const [open, setOpen] = React.useState(false)
  const itemRefs = React.useRef<Array<HTMLButtonElement | null>>([])
  const [activeIndex, setActiveIndex] = React.useState<number>(-1)

  // Reset focus state when menu reopens.
  React.useEffect(() => {
    if (open) {
      setActiveIndex(-1)
      itemRefs.current = []
    }
  }, [open])

  const focusableIndices = React.useMemo(
    () =>
      items
        .map((item, idx) => ({ item, idx }))
        .filter(({ item }) => !item.divider && !item.disabled)
        .map(({ idx }) => idx),
    [items],
  )

  const moveFocus = (delta: 1 | -1) => {
    if (focusableIndices.length === 0) return
    const currentPos = focusableIndices.indexOf(activeIndex)
    const nextPos =
      currentPos === -1
        ? delta > 0
          ? 0
          : focusableIndices.length - 1
        : (currentPos + delta + focusableIndices.length) % focusableIndices.length
    const nextIdx = focusableIndices[nextPos]
    setActiveIndex(nextIdx)
    itemRefs.current[nextIdx]?.focus()
  }

  const handleKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault()
      moveFocus(1)
    } else if (event.key === "ArrowUp") {
      event.preventDefault()
      moveFocus(-1)
    }
  }

  return (
    <Popover
      trigger={trigger}
      placement={placement}
      open={open}
      onOpenChange={setOpen}
      className={cn("p-1", className)}
    >
      <div
        role="menu"
        className={cn("flex flex-col min-w-[14rem]", menuClassName)}
        onKeyDown={handleKeyDown}
      >
        {items.map((item, index) => {
          if (item.divider) {
            return (
              <div
                key={item.id ?? `divider-${index}`}
                role="separator"
                className="h-px my-1 mx-1 bg-[var(--color-border-default)]"
              />
            )
          }
          const Icon = item.icon
          return (
            <button
              key={item.id ?? `${item.label}-${index}`}
              type="button"
              role="menuitem"
              ref={(el) => {
                itemRefs.current[index] = el
              }}
              disabled={item.disabled}
              onClick={() => {
                item.onClick?.()
                setOpen(false)
              }}
              className={cn(
                "w-full flex items-center gap-2 px-2.5 py-1.5 text-sm text-left rounded-sm outline-none",
                "hover:bg-surface-muted focus-visible:bg-surface-muted",
                item.danger ? "text-danger" : "text-secondary",
                item.disabled && "opacity-50 cursor-not-allowed",
              )}
            >
              {Icon && <Icon className="w-3.5 h-3.5 shrink-0" />}
              <span className="flex-1 truncate">{item.label}</span>
              {item.shortcut && (
                <span className="ml-2 text-[10px] uppercase tracking-wider text-muted font-mono">
                  {item.shortcut}
                </span>
              )}
            </button>
          )
        })}
      </div>
    </Popover>
  )
}
