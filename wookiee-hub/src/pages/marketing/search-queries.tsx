import * as DropdownMenu from "@radix-ui/react-dropdown-menu"
import { ChevronDown, Plus } from "lucide-react"
import { useSearchParams } from "react-router-dom"
import { Button } from "@/components/crm/ui/Button"
import { SearchQueriesTable } from "./search-queries/SearchQueriesTable"
import { AddBrandQueryPanel } from "./search-queries/AddBrandQueryPanel"
import { AddWWPanel } from "./search-queries/AddWWPanel"
import { AddNomenclaturePanel } from "./search-queries/AddNomenclaturePanel"
import { SearchQueryDetailPanel } from "./search-queries/SearchQueryDetailPanel"

const LAST = new Date().toISOString().slice(0, 10)

function AddMenu() {
  const [, setParams] = useSearchParams()

  const open = (kind: 'brand' | 'nm' | 'ww') =>
    setParams((p) => { p.set('add', kind); return p })

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <Button variant="primary" className="gap-1">
          <Plus className="w-4 h-4" aria-hidden />
          Добавить
          <ChevronDown className="w-3.5 h-3.5 opacity-70" aria-hidden />
        </Button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="end"
          sideOffset={4}
          className="z-50 bg-popover border border-border rounded-lg shadow-md py-1 min-w-[220px]"
        >
          <DropdownMenu.Item
            onSelect={() => open('brand')}
            className="flex items-center gap-2 px-3 py-2 text-sm hover:bg-muted cursor-pointer outline-none data-[highlighted]:bg-muted"
          >
            Брендированный запрос
          </DropdownMenu.Item>
          <DropdownMenu.Item
            onSelect={() => open('nm')}
            className="flex items-center gap-2 px-3 py-2 text-sm hover:bg-muted cursor-pointer outline-none data-[highlighted]:bg-muted"
          >
            Артикул WB (номенклатура)
          </DropdownMenu.Item>
          <DropdownMenu.Item
            onSelect={() => open('ww')}
            className="flex items-center gap-2 px-3 py-2 text-sm hover:bg-muted cursor-pointer outline-none data-[highlighted]:bg-muted"
          >
            Подменка WW
          </DropdownMenu.Item>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  )
}

type ActivePanel =
  | { kind: 'add-brand' }
  | { kind: 'add-nm' }
  | { kind: 'add-ww' }
  | { kind: 'detail'; unifiedId: string }
  | null

export function SearchQueriesPage() {
  const [params, setParams] = useSearchParams()
  const addParam  = params.get('add')   // 'brand' | 'nm' | 'ww' | null
  const openParam = params.get('open')  // unified_id | null
  const dateFrom  = params.get('from') ?? '2026-03-30'
  const dateTo    = params.get('to')   ?? LAST

  const closeAdd    = () => setParams((p) => { p.delete('add');  return p })
  const closeDetail = () => setParams((p) => { p.delete('open'); return p })

  const active: ActivePanel =
    addParam === 'brand' ? { kind: 'add-brand' } :
    addParam === 'nm'    ? { kind: 'add-nm' } :
    addParam === 'ww'    ? { kind: 'add-ww' } :
    openParam            ? { kind: 'detail', unifiedId: openParam } :
    null

  // All panels (Add + Detail) render as overlay Drawer so the table behind never shrinks.
  // Previously detail used a 560px split-pane on lg+, which clipped the right 4 columns
  // (CR корз / Корз / CR зак / Заказы / CRV) at viewport ≤ 1600.
  const renderPanel = () => {
    if (!active) return null
    if (active.kind === 'add-brand') return <AddBrandQueryPanel onClose={closeAdd} mode="drawer" />
    if (active.kind === 'add-nm')    return <AddNomenclaturePanel onClose={closeAdd} />
    if (active.kind === 'add-ww')    return <AddWWPanel onClose={closeAdd} mode="drawer" />
    return (
      <SearchQueryDetailPanel
        unifiedId={active.unifiedId}
        dateFrom={dateFrom}
        dateTo={dateTo}
        onClose={closeDetail}
        mode="drawer"
      />
    )
  }

  return (
    <div className="flex flex-1 overflow-hidden">
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        <div className="px-6 pt-6 pb-0">
          <div className="flex items-end justify-between mb-6">
            <div>
              <h1
                className="text-stone-900"
                style={{ fontFamily: "'Instrument Serif', serif", fontSize: 24, fontStyle: "italic" }}
              >
                Поисковые запросы
              </h1>
              <p className="text-sm text-stone-500 mt-0.5">Брендовые, артикулы и подменные WW-коды</p>
            </div>
            <AddMenu />
          </div>
        </div>
        <SearchQueriesTable />
      </div>

      {renderPanel()}
    </div>
  )
}
