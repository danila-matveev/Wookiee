import * as Dialog from '@radix-ui/react-dialog'
import { X } from 'lucide-react'
import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

/**
 * Width tokens map to fixed pixel widths (overrides Tailwind max-w defaults so
 * the drawer keeps its target overlay width regardless of viewport class breakpoints).
 *   sm = 420px, md = 520px, lg = 720px, xl = 920px
 *
 * For backward compatibility a raw Tailwind class string is still accepted
 * (e.g. width="max-w-3xl" used by influence drawers).
 */
type DrawerWidth = 'sm' | 'md' | 'lg' | 'xl' | (string & {})

interface DrawerProps {
  open: boolean
  onClose: () => void
  title: string
  children: ReactNode
  footer?: ReactNode
  width?: DrawerWidth
}

const WIDTH_TOKENS: Record<'sm' | 'md' | 'lg' | 'xl', string> = {
  sm: 'w-[420px] max-w-full',
  md: 'w-[520px] max-w-full',
  lg: 'w-[720px] max-w-full',
  xl: 'w-[920px] max-w-full',
}

type WidthToken = keyof typeof WIDTH_TOKENS

function isWidthToken(w: DrawerWidth): w is WidthToken {
  return w === 'sm' || w === 'md' || w === 'lg' || w === 'xl'
}

function resolveWidth(width: DrawerWidth): { className: string; useFullWidth: boolean } {
  if (isWidthToken(width)) {
    return { className: WIDTH_TOKENS[width], useFullWidth: false }
  }
  // Legacy string (Tailwind class) — keep `w-full` baseline so max-w-* takes effect.
  return { className: width, useFullWidth: true }
}

export function Drawer({
  open, onClose, title, children, footer, width = 'max-w-2xl',
}: DrawerProps) {
  const { className: widthClass, useFullWidth } = resolveWidth(width)
  return (
    <Dialog.Root open={open} onOpenChange={(o) => { if (!o) onClose() }}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/30 z-40 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 duration-200" />
        <Dialog.Content
          className={cn(
            'fixed inset-y-0 right-0 z-50 flex flex-col bg-card',
            useFullWidth && 'w-full',
            widthClass,
            'data-[state=open]:animate-in data-[state=closed]:animate-out',
            'data-[state=closed]:slide-out-to-right data-[state=open]:slide-in-from-right',
            'duration-200',
          )}
          style={{ boxShadow: '-16px 0 60px -12px rgba(0,0,0,0.18)' }}
        >
          <header className="px-6 py-4 border-b border-border flex items-center justify-between shrink-0">
            <Dialog.Title className="font-semibold text-lg text-fg truncate pr-3">{title}</Dialog.Title>
            <button
              type="button"
              aria-label="Закрыть"
              className="p-2 -mr-1 rounded-md text-stone-500 hover:bg-stone-100 hover:text-stone-900 cursor-pointer shrink-0"
              onClick={onClose}
            >
              <X size={20} />
            </button>
          </header>
          <div className="flex-1 overflow-y-auto px-6 py-4">{children}</div>
          {footer && (
            <footer className="px-6 py-4 border-t border-border flex justify-end gap-2 shrink-0">
              {footer}
            </footer>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
