import { useEffect } from "react"
import { Search } from "lucide-react"

// TODO(wave-1-A3): replace this stub with the real CommandPalette
// (search across modeli, cveta, barkody, OZON-артикулы, WB-номенклатуры
// via service.searchGlobal()). For now this only renders an empty modal.

export interface CommandPaletteProps {
  open: boolean
  onClose: () => void
}

export function CommandPalette({ open, onClose }: CommandPaletteProps) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose()
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [open, onClose])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 bg-stone-900/40 flex items-start justify-center pt-[10vh]"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Поиск по каталогу"
    >
      <div
        className="w-full max-w-xl bg-white rounded-xl shadow-2xl overflow-hidden border border-stone-200"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-3 px-4 py-3 border-b border-stone-200">
          <Search className="w-4 h-4 text-stone-400" />
          <input
            autoFocus
            placeholder="Найти модель, цвет, баркод…"
            className="flex-1 outline-none text-sm placeholder:text-stone-400 bg-transparent text-stone-900"
          />
          <kbd className="text-[10px] text-stone-400 border border-stone-300 rounded px-1 py-0.5">
            esc
          </kbd>
        </div>
        <div className="p-6 text-center text-sm text-stone-400">
          Поиск будет реализован в Wave 1 A3
        </div>
      </div>
    </div>
  )
}
