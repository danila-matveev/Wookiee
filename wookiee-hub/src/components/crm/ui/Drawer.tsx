import * as Dialog from '@radix-ui/react-dialog'
import { X } from 'lucide-react'
import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface DrawerProps {
  open: boolean
  onClose: () => void
  title: string
  children: ReactNode
  footer?: ReactNode
  width?: string
}

export function Drawer({
  open, onClose, title, children, footer, width = 'max-w-2xl',
}: DrawerProps) {
  return (
    <Dialog.Root open={open} onOpenChange={(o) => { if (!o) onClose() }}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/30 z-40 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 duration-200" />
        <Dialog.Content
          className={cn(
            'fixed inset-y-0 right-0 z-50 flex flex-col bg-card',
            'w-full', width,
            'data-[state=open]:animate-in data-[state=closed]:animate-out',
            'data-[state=closed]:slide-out-to-right data-[state=open]:slide-in-from-right',
            'duration-200',
          )}
          style={{ boxShadow: '-16px 0 60px -12px rgba(0,0,0,0.18)' }}
        >
          <header className="px-6 py-4 border-b border-border flex items-center justify-between shrink-0">
            <Dialog.Title className="font-semibold text-lg text-fg">{title}</Dialog.Title>
            <button
              type="button"
              aria-label="Закрыть"
              className="p-2 rounded-md hover:bg-primary-light cursor-pointer"
              onClick={onClose}
            >
              <X size={18} />
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
