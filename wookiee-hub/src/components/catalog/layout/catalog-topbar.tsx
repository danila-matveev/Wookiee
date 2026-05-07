import { useLocation } from "react-router-dom"
import { ChevronRight, Search } from "lucide-react"
import { useState, useEffect } from "react"

const BREADCRUMB_MAP: Record<string, string> = {
  catalog: "Каталог",
  matrix: "Матрица товаров",
  colors: "Цвета",
  skleyki: "Склейки МП",
  references: "Справочники",
  kategorii: "Категории",
  kollekcii: "Коллекции",
  fabriki: "Производители",
  importery: "Юрлица",
  razmery: "Размеры",
  statusy: "Статусы",
}

export function CatalogTopBar() {
  const { pathname } = useLocation()
  const [searchOpen, setSearchOpen] = useState(false)

  const segments = pathname.split("/").filter(Boolean)
  const crumbs = segments.map((s) => BREADCRUMB_MAP[s] ?? s)

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault()
        setSearchOpen(true)
      }
      if (e.key === "Escape") setSearchOpen(false)
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [])

  return (
    <div className="h-14 border-b border-stone-200 bg-white flex items-center px-6 gap-4 shrink-0">
      <div className="flex items-center gap-2 text-sm text-stone-500 min-w-0 flex-1">
        {crumbs.map((c, i) => (
          <span key={i} className="flex items-center gap-2">
            {i > 0 && (
              <ChevronRight className="w-3.5 h-3.5 text-stone-300 shrink-0" />
            )}
            <span
              className={
                i === crumbs.length - 1
                  ? "text-stone-900 font-medium truncate"
                  : "truncate"
              }
            >
              {c}
            </span>
          </span>
        ))}
      </div>
      <button
        onClick={() => setSearchOpen(true)}
        className="flex items-center gap-2 px-3 py-1.5 text-sm text-stone-500 bg-stone-100 hover:bg-stone-200 rounded-md transition-colors min-w-[260px]"
      >
        <Search className="w-3.5 h-3.5" />
        <span className="flex-1 text-left">Поиск по баркоду, артикулу…</span>
        <kbd className="text-[10px] text-stone-400 border border-stone-300 rounded px-1 py-0.5 font-mono">
          ⌘K
        </kbd>
      </button>

      {/* Command palette placeholder */}
      {searchOpen && (
        <div
          className="fixed inset-0 z-50 bg-stone-900/40 flex items-start justify-center pt-[10vh]"
          onClick={() => setSearchOpen(false)}
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
                className="flex-1 outline-none text-sm placeholder:text-stone-400"
              />
              <kbd className="text-[10px] text-stone-400 border border-stone-300 rounded px-1 py-0.5">
                esc
              </kbd>
            </div>
            <div className="p-6 text-center text-sm text-stone-400">
              Поиск будет реализован в Спринте 4
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
