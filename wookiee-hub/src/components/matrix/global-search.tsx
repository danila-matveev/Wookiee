import { useCallback, useEffect, useState } from "react"
import { Search } from "lucide-react"
import { Input } from "@/components/ui/input"
import {
  Dialog,
  DialogContent,
} from "@/components/ui/dialog"
import { useMatrixStore, type MatrixEntity } from "@/stores/matrix-store"
import { matrixApi, type SearchResult } from "@/lib/matrix-api"

const ENTITY_LABELS: Record<string, string> = {
  modeli_osnova: "Модели основы",
  modeli: "Подмодели",
  artikuly: "Артикулы",
  tovary: "Товары",
  cveta: "Цвета",
  fabriki: "Фабрики",
  importery: "Импортёры",
  skleyki_wb: "Склейки WB",
  skleyki_ozon: "Склейки Ozon",
  sertifikaty: "Сертификаты",
}

// Map search entity names to sidebar entity names
const ENTITY_TO_PAGE: Record<string, MatrixEntity> = {
  modeli_osnova: "models",
  modeli: "models",
  artikuly: "articles",
  tovary: "products",
  cveta: "colors",
  fabriki: "factories",
  importery: "importers",
  skleyki_wb: "cards-wb",
  skleyki_ozon: "cards-ozon",
  sertifikaty: "certs",
}

export function GlobalSearch() {
  const searchOpen = useMatrixStore((s) => s.searchOpen)
  const setSearchOpen = useMatrixStore((s) => s.setSearchOpen)
  const setActiveEntity = useMatrixStore((s) => s.setActiveEntity)
  const openDetailPanel = useMatrixStore((s) => s.openDetailPanel)

  const [query, setQuery] = useState("")
  const [results, setResults] = useState<SearchResult[]>([])
  const [loading, setLoading] = useState(false)

  // Keyboard shortcut
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault()
        setSearchOpen(!searchOpen)
      }
    }
    document.addEventListener("keydown", handler)
    return () => document.removeEventListener("keydown", handler)
  }, [searchOpen, setSearchOpen])

  // Debounced search
  useEffect(() => {
    if (!query || query.length < 2) {
      setResults([])
      return
    }
    const timer = setTimeout(async () => {
      setLoading(true)
      try {
        const res = await matrixApi.search(query, 20)
        setResults(res.results)
      } catch {
        setResults([])
      } finally {
        setLoading(false)
      }
    }, 300)
    return () => clearTimeout(timer)
  }, [query])

  const handleSelect = useCallback(
    (result: SearchResult) => {
      const page = ENTITY_TO_PAGE[result.entity]
      if (page) {
        setActiveEntity(page)
        openDetailPanel(result.id, page)
      }
      setSearchOpen(false)
      setQuery("")
    },
    [setActiveEntity, openDetailPanel, setSearchOpen],
  )

  // Group results by entity
  const grouped = results.reduce<Record<string, SearchResult[]>>((acc, r) => {
    ;(acc[r.entity] ??= []).push(r)
    return acc
  }, {})

  return (
    <Dialog open={searchOpen} onOpenChange={setSearchOpen}>
      <DialogContent className="max-w-lg gap-0 p-0">
        <div className="flex items-center gap-2 border-b px-3">
          <Search className="h-4 w-4 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Поиск по всем сущностям..."
            className="border-0 shadow-none focus-visible:ring-0"
            autoFocus
          />
        </div>

        <div className="max-h-80 overflow-y-auto p-2">
          {loading && (
            <div className="p-4 text-center text-sm text-muted-foreground">
              Поиск...
            </div>
          )}

          {!loading && query.length >= 2 && results.length === 0 && (
            <div className="p-4 text-center text-sm text-muted-foreground">
              Ничего не найдено
            </div>
          )}

          {Object.entries(grouped).map(([entity, items]) => (
            <div key={entity}>
              <div className="px-2 py-1 text-xs font-medium text-muted-foreground">
                {ENTITY_LABELS[entity] ?? entity}
              </div>
              {items.map((item) => (
                <button
                  key={`${item.entity}-${item.id}`}
                  className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-accent"
                  onClick={() => handleSelect(item)}
                >
                  <span className="font-medium">{item.name}</span>
                  {item.match_field !== "name" && (
                    <span className="text-muted-foreground">
                      {item.match_field}: {item.match_text}
                    </span>
                  )}
                </button>
              ))}
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  )
}
