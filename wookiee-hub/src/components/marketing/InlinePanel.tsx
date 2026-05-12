import type { ReactNode } from 'react'
import { X } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface InlinePanelProps {
  title: ReactNode
  onClose: () => void
  children: ReactNode
  footer?: ReactNode
  width?: number
  className?: string
}

/**
 * Right-side inline panel for split-pane layouts (list left + panel right).
 * Unlike `<Drawer/>`, it does NOT overlay the page — it lives inside the flex row
 * and shrinks the list to make room. Matches the marketing v4 spec pattern:
 * `<div className="w-[420px] shrink-0 border-l border-border bg-card flex flex-col h-full overflow-hidden">`.
 */
export function InlinePanel({ title, onClose, children, footer, width = 420, className }: InlinePanelProps) {
  return (
    <div
      className={cn(
        'shrink-0 border-l border-border bg-card flex flex-col h-full overflow-hidden',
        className,
      )}
      style={{ width: `${width}px` }}
      role="complementary"
    >
      <header className="px-5 py-4 border-b border-border flex items-start justify-between shrink-0 gap-3">
        <div className="flex-1 min-w-0">{title}</div>
        <button
          type="button"
          aria-label="Закрыть"
          onClick={onClose}
          className="p-1.5 rounded-md text-muted-foreground hover:bg-muted shrink-0"
        >
          <X className="w-3.5 h-3.5" aria-hidden />
        </button>
      </header>
      <div className="flex-1 overflow-y-auto">{children}</div>
      {footer && (
        <footer className="px-5 py-3 border-t border-border flex justify-end gap-2 shrink-0">
          {footer}
        </footer>
      )}
    </div>
  )
}
