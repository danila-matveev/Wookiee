import * as DropdownMenu from "@radix-ui/react-dropdown-menu"
import { ChevronDown, Plus } from "lucide-react"
import { useSearchParams } from "react-router-dom"
import { PageHeader } from "@/components/crm/layout/PageHeader"
import { Button } from "@/components/crm/ui/Button"
import { SearchQueriesTable } from "./search-queries/SearchQueriesTable"
import { AddBrandQueryPanel } from "./search-queries/AddBrandQueryPanel"
import { AddWWPanel } from "./search-queries/AddWWPanel"
import { SearchQueryDetailPanel } from "./search-queries/SearchQueryDetailPanel"

const LAST = new Date().toISOString().slice(0, 10)

/**
 * Spec wookiee_marketing_v4.jsx (line 552) предлагает одну кнопку «+ Добавить WW-код»,
 * но у нас два потока: брендовый запрос и WW-код. Сохраняем dropdown с двумя пунктами.
 */
function AddMenu() {
  const [, setParams] = useSearchParams()

  const openBrand = () =>
    setParams((p) => { p.set('add', 'brand'); return p })

  const openWW = () =>
    setParams((p) => { p.set('add', 'ww'); return p })

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
          className="z-50 bg-popover border border-border rounded-lg shadow-md py-1 min-w-[200px]"
        >
          <DropdownMenu.Item
            onSelect={openBrand}
            className="flex items-center gap-2 px-3 py-2 text-sm hover:bg-muted cursor-pointer outline-none data-[highlighted]:bg-muted"
          >
            Брендированный запрос
          </DropdownMenu.Item>
          <DropdownMenu.Item
            onSelect={openWW}
            className="flex items-center gap-2 px-3 py-2 text-sm hover:bg-muted cursor-pointer outline-none data-[highlighted]:bg-muted"
          >
            WW-код
          </DropdownMenu.Item>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  )
}

export function SearchQueriesPage() {
  const [params, setParams] = useSearchParams()
  const addParam  = params.get('add')
  const openParam = params.get('open')
  const dateFrom  = params.get('from') ?? '2026-03-30'
  const dateTo    = params.get('to')   ?? LAST

  const closeAdd = () =>
    setParams((p) => { p.delete('add'); return p })

  const closeOpen = () =>
    setParams((p) => { p.delete('open'); return p })

  // Detail panel and AddBrandQueryPanel render in the right rail (split-pane);
  // AddWWPanel still uses its own modal Drawer, so it does NOT take rail space.
  const railContent = openParam ? (
    <SearchQueryDetailPanel
      unifiedId={openParam}
      dateFrom={dateFrom}
      dateTo={dateTo}
      onClose={closeOpen}
    />
  ) : addParam === 'brand' ? (
    <AddBrandQueryPanel onClose={closeAdd} />
  ) : null

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="px-6 pt-6 pb-0 shrink-0">
        <PageHeader
          title="Поисковые запросы"
          sub="Брендовые, артикулы и подменные WW-коды"
          actions={<AddMenu />}
        />
      </div>
      <div className="flex flex-1 overflow-hidden min-h-0">
        <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
          <SearchQueriesTable selectedId={openParam} />
        </div>
        {railContent}
      </div>
      {addParam === 'ww' && <AddWWPanel onClose={closeAdd} />}
    </div>
  )
}
