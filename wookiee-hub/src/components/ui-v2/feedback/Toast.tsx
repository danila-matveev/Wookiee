import * as React from "react"
import { createPortal } from "react-dom"
import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Info as InfoIcon,
  Bell,
  Loader2,
  X,
} from "lucide-react"
import { cn } from "@/lib/utils"

export type ToastVariant =
  | "default"
  | "success"
  | "warning"
  | "danger"
  | "info"
  | "loading"

export interface ToastOptions {
  /** Variant — controls icon + accent color. */
  variant?: ToastVariant
  /** Optional second line (description). */
  description?: string
  /** Auto-dismiss timeout in ms. Default 4000.
   *  Use 0 to keep until manual close. `loading` variant defaults to 0. */
  duration?: number
  /** Stable id — if omitted, auto-generated. Useful to dedupe / update. */
  id?: string
  /** Optional action element shown next to dismiss. */
  action?: React.ReactNode
}

export interface ToastInstance {
  id: string
  title: string
  description?: string
  variant: ToastVariant
  duration: number
  action?: React.ReactNode
  createdAt: number
}

/* ────────────────────────────────────────────────────────────
 * Toast singleton store. Allows useToast() outside <ToastProvider>
 * via the same shared bus.
 * ──────────────────────────────────────────────────────────── */

type Listener = (toasts: ToastInstance[]) => void

interface ToastStore {
  getSnapshot: () => ToastInstance[]
  subscribe: (listener: Listener) => () => void
  push: (title: string, options?: ToastOptions) => string
  dismiss: (id: string) => void
  clear: () => void
}

function createToastStore(): ToastStore {
  let toasts: ToastInstance[] = []
  const listeners = new Set<Listener>()
  let counter = 0

  const emit = () => {
    for (const l of listeners) l(toasts)
  }

  const dismiss = (id: string) => {
    const next = toasts.filter((t) => t.id !== id)
    if (next.length === toasts.length) return
    toasts = next
    emit()
  }

  return {
    getSnapshot: () => toasts,
    subscribe: (listener) => {
      listeners.add(listener)
      return () => {
        listeners.delete(listener)
      }
    },
    push: (title, options) => {
      counter += 1
      const id = options?.id ?? `toast-${Date.now()}-${counter}`
      const variant = options?.variant ?? "default"
      // Loading toasts never auto-dismiss unless caller overrides.
      const defaultDuration = variant === "loading" ? 0 : 4000
      const next: ToastInstance = {
        id,
        title,
        description: options?.description,
        variant,
        duration: options?.duration ?? defaultDuration,
        action: options?.action,
        createdAt: Date.now(),
      }
      // Replace if same id, otherwise append.
      const without = toasts.filter((t) => t.id !== id)
      toasts = [...without, next]
      emit()
      return id
    },
    dismiss,
    clear: () => {
      if (toasts.length === 0) return
      toasts = []
      emit()
    },
  }
}

const store = createToastStore()

/* ────────────────────────────────────────────────────────────
 * Public API: useToast hook
 * ──────────────────────────────────────────────────────────── */

export interface UseToastReturn {
  /** Show toast. Returns id for later dismiss. */
  toast: (title: string, options?: ToastOptions) => string
  /**
   * Show a loading toast (Loader2 spinning, no auto-dismiss).
   * Returns id — caller dismisses via {@link dismiss}.
   */
  loading: (title: string, options?: Omit<ToastOptions, "variant">) => string
  /** Dismiss specific toast by id. */
  dismiss: (id: string) => void
  /** Clear all toasts. */
  clear: () => void
}

export function useToast(): UseToastReturn {
  return React.useMemo(
    () => ({
      toast: (title, options) => store.push(title, options),
      loading: (title, options) =>
        store.push(title, { ...options, variant: "loading" }),
      dismiss: (id) => store.dismiss(id),
      clear: () => store.clear(),
    }),
    [],
  )
}

/* ────────────────────────────────────────────────────────────
 * Toast component (single visual unit)
 * ──────────────────────────────────────────────────────────── */

const variantIcon: Record<ToastVariant, React.ComponentType<{ className?: string }>> = {
  default: Bell,
  success: CheckCircle2,
  warning: AlertTriangle,
  danger: XCircle,
  info: InfoIcon,
  loading: Loader2,
}

const variantAccent: Record<ToastVariant, string> = {
  default: "text-muted",
  success: "text-success",
  warning: "text-warning",
  danger: "text-danger",
  info: "text-info",
  loading: "text-muted animate-spin",
}

export interface ToastProps {
  variant?: ToastVariant
  title: string
  description?: string
  action?: React.ReactNode
  onClose?: () => void
  className?: string
}

export function Toast({
  variant = "default",
  title,
  description,
  action,
  onClose,
  className,
}: ToastProps) {
  const Icon = variantIcon[variant]
  return (
    <div
      role="status"
      className={cn(
        "pointer-events-auto flex items-start gap-3 w-[22rem] max-w-[calc(100vw-2rem)]",
        "bg-elevated border border-default rounded-md p-3",
        "shadow-[var(--shadow-md)]",
        className,
      )}
    >
      <Icon className={cn("w-4 h-4 mt-0.5 shrink-0", variantAccent[variant])} aria-hidden />
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-primary truncate">{title}</div>
        {description && <div className="text-xs text-muted mt-0.5">{description}</div>}
      </div>
      {action}
      {onClose && (
        <button
          type="button"
          onClick={onClose}
          aria-label="Закрыть"
          className="p-0.5 rounded text-muted hover:bg-surface-muted transition-colors"
        >
          <X className="w-3.5 h-3.5" aria-hidden />
        </button>
      )}
    </div>
  )
}

/* ────────────────────────────────────────────────────────────
 * Individual toast wrapper (handles its own dismiss timer).
 * ──────────────────────────────────────────────────────────── */

interface ToastItemProps {
  toast: ToastInstance
  onDismiss: (id: string) => void
}

function ToastItem({ toast, onDismiss }: ToastItemProps) {
  React.useEffect(() => {
    if (!toast.duration || toast.duration <= 0) return
    const timer = window.setTimeout(() => onDismiss(toast.id), toast.duration)
    return () => window.clearTimeout(timer)
  }, [toast.id, toast.duration, onDismiss])

  return (
    <Toast
      variant={toast.variant}
      title={toast.title}
      description={toast.description}
      action={toast.action}
      onClose={() => onDismiss(toast.id)}
    />
  )
}

/* ────────────────────────────────────────────────────────────
 * ToastProvider — mounts the toast viewport.
 * Toast state lives in the singleton store, so the provider is
 * essentially a portal-renderer. Multiple providers will share
 * the same store but each renders its own viewport — mount once.
 * ──────────────────────────────────────────────────────────── */

export interface ToastProviderProps {
  children?: React.ReactNode
}

export function ToastProvider({ children }: ToastProviderProps) {
  const toasts = React.useSyncExternalStore(
    store.subscribe,
    store.getSnapshot,
    store.getSnapshot,
  )

  const onDismiss = React.useCallback((id: string) => {
    store.dismiss(id)
  }, [])

  // Render-time check for SSR-safety (vite dev is CSR but be defensive).
  const portalTarget = typeof document !== "undefined" ? document.body : null

  return (
    <>
      {children}
      {portalTarget &&
        createPortal(
          <div
            aria-live="polite"
            aria-label="Уведомления"
            className="fixed bottom-4 right-4 flex flex-col gap-2 pointer-events-none"
            style={{ zIndex: "var(--z-toast)" }}
          >
            {toasts.map((toast) => (
              <ToastItem key={toast.id} toast={toast} onDismiss={onDismiss} />
            ))}
          </div>,
          portalTarget,
        )}
    </>
  )
}
