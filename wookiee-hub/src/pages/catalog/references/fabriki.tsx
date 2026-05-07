import { useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { Plus } from "lucide-react"
import { CatalogTable, type TableColumn } from "@/components/catalog/layout/catalog-table"
import { useReference } from "./_use-reference"
import { fetchFabriki, insertFabrika } from "@/lib/catalog/service"
import { PageHeader, ErrorBlock, SkeletonTable, RefModal } from "./_shared"
import type { Fabrika } from "@/types/catalog"

const COLUMNS: TableColumn<Fabrika>[] = [
  { key: "id",       label: "ID",       mono: true, dim: true },
  { key: "nazvanie", label: "Название" },
  { key: "strana",   label: "Страна",   dim: true },
]

export function FabrikiPage() {
  const [modalOpen, setModalOpen] = useState(false)
  const qc = useQueryClient()
  const { data = [], isLoading, error } = useReference("fabriki", fetchFabriki)

  const handleAdd = async (values: Record<string, string>) => {
    await insertFabrika({
      nazvanie: values.nazvanie,
      strana: values.strana || undefined,
    })
    await qc.invalidateQueries({ queryKey: ["catalog", "reference", "fabriki"] })
  }

  return (
    <div className="px-6 py-6 max-w-4xl">
      <div className="flex items-center justify-between mb-4">
        <PageHeader title="Производители" count={data.length} isLoading={isLoading} />
        <button
          onClick={() => setModalOpen(true)}
          className="px-3 py-1.5 text-xs text-white bg-stone-900 hover:bg-stone-800 rounded-md flex items-center gap-1.5"
        >
          <Plus className="w-3.5 h-3.5" /> Добавить
        </button>
      </div>
      {error && <ErrorBlock message={error.message} />}
      {isLoading ? (
        <SkeletonTable rows={5} cols={3} />
      ) : (
        <CatalogTable columns={COLUMNS} data={data} emptyText="Производители не найдены" />
      )}
      {modalOpen && (
        <RefModal
          title="Новый производитель"
          fields={[
            { key: "nazvanie", label: "Название" },
            { key: "strana", label: "Страна", placeholder: "Китай" },
          ]}
          onSave={handleAdd}
          onClose={() => setModalOpen(false)}
        />
      )}
    </div>
  )
}
