import { Dialog, Transition } from '@headlessui/react';
import { X } from 'lucide-react';
import { Fragment, type ReactNode } from 'react';

export function Drawer({
  open,
  onClose,
  title,
  children,
  footer,
  width = 'max-w-2xl',
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
  width?: string;
}) {
  return (
    <Transition show={open} as={Fragment}>
      <Dialog as="div" className="relative z-40" onClose={onClose}>
        <Transition.Child
          as={Fragment}
          enter="transition-opacity duration-200"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="transition-opacity duration-150"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black/30" />
        </Transition.Child>
        <div className="fixed inset-0 flex justify-end">
          <Transition.Child
            as={Fragment}
            enter="transition-transform duration-200"
            enterFrom="translate-x-full"
            enterTo="translate-x-0"
            leave="transition-transform duration-150"
            leaveFrom="translate-x-0"
            leaveTo="translate-x-full"
          >
            <Dialog.Panel
              className={`w-full ${width} max-h-screen overflow-hidden bg-card shadow-[var(--shadow-drawer)] flex flex-col`}
            >
              <header className="px-6 py-4 border-b border-border flex items-center justify-between">
                <Dialog.Title className="font-display font-bold text-lg">{title}</Dialog.Title>
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
                <footer className="px-6 py-4 border-t border-border flex justify-end gap-2">
                  {footer}
                </footer>
              )}
            </Dialog.Panel>
          </Transition.Child>
        </div>
      </Dialog>
    </Transition>
  );
}
