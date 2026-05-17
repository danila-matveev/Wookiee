import { Link, useLocation, useSearchParams } from "react-router-dom"
import { ArrowLeft, ChevronRight, Search } from "lucide-react"

import { getRouteLabel } from "@/lib/catalog/route-labels"

// Map root catalog → "Каталог > Матрица" (matrix is the default).
// W10.16 — лейблы вынесены в `src/lib/catalog/route-labels.ts`. Здесь только
// логика построения цепочки (порядок сегментов, дефолт «Матрица» на /catalog,
// добавление KOD из ?model/?color как последний crumb).
function buildCrumbs(pathname: string, modelKod: string | null, colorCode: string | null): string[] {
  const segments = pathname.split("/").filter(Boolean)
  const crumbs: string[] = segments.map((seg) => getRouteLabel(seg))
  // For pretty hub UX: when on /catalog (root) without children, append "Матрица"
  if (segments.length === 1 && segments[0] === "catalog") {
    crumbs.push("Матрица")
  }
  // Append modal context (?model=KOD or ?color=KOD) as a deeper crumb
  if (modelKod) crumbs.push(modelKod)
  else if (colorCode) crumbs.push(colorCode)
  return crumbs
}

export interface CatalogTopBarProps {
  onOpenSearch: () => void
}

export function CatalogTopBar({ onOpenSearch }: CatalogTopBarProps) {
  const { pathname } = useLocation()
  const [searchParams] = useSearchParams()
  const modelKod = searchParams.get("model")
  const colorCode = searchParams.get("color")
  const crumbs = buildCrumbs(pathname, modelKod, colorCode)

  return (
    <div className="h-14 border-b border-stone-200 bg-white flex items-center px-6 gap-4 shrink-0 sticky top-0 z-20">
      <Link
        to="/"
        aria-label="Назад в Hub"
        className="flex items-center gap-1.5 px-2 py-1 rounded-md text-sm text-stone-500 hover:text-stone-900 hover:bg-stone-100 transition-colors shrink-0"
      >
        <ArrowLeft size={14} aria-hidden />
        <span className="hidden sm:inline">В Hub</span>
      </Link>
      <div className="flex items-center gap-2 text-sm text-stone-500 min-w-0 flex-1">
        {crumbs.map((c, i) => (
          <span key={`${c}-${i}`} className="flex items-center gap-2 min-w-0">
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
        type="button"
        onClick={onOpenSearch}
        className="flex items-center gap-2 px-3 py-1.5 text-sm text-stone-500 bg-stone-100 hover:bg-stone-200 rounded-md transition-colors min-w-[260px]"
        aria-label="Открыть поиск по каталогу (⌘K)"
      >
        <Search className="w-3.5 h-3.5" />
        <span className="flex-1 text-left">Поиск по баркоду, артикулу…</span>
        <kbd className="text-[10px] text-stone-400 border border-stone-300 rounded px-1 py-0.5 font-mono">
          ⌘K
        </kbd>
      </button>
    </div>
  )
}
