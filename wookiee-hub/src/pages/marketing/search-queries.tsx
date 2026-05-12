import * as DropdownMenu from "@radix-ui/react-dropdown-menu"
import { ChevronDown, Plus } from "lucide-react"
import { useSearchParams } from "react-router-dom"
import { Button } from "@/components/crm/ui/Button"
import { SearchQueriesTable } from "./search-queries/SearchQueriesTable"
import { AddBrandQueryPanel } from "./search-queries/AddBrandQueryPanel"
import { AddWWPanel } from "./search-queries/AddWWPanel"

function AddMenu() {
  const [params, setParams] = useSearchParams()

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
  const addParam = params.get('add')

  const closeAdd = () =>
    setParams((p) => { p.delete('add'); return p })

  return (
    <div className="flex flex-col h-full">
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
      {addParam === 'brand' && <AddBrandQueryPanel onClose={closeAdd} />}
      {addParam === 'ww' && <AddWWPanel onClose={closeAdd} />}
    </div>
  )
}
