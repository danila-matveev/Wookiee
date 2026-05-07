import { useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { Plus } from "lucide-react"
import { CatalogTable, type TableColumn } from "@/components/catalog/layout/catalog-table"
import { useReference } from "./_use-reference"
import { fetchKollekcii, insertKollekciya } from "@/lib/catalog/service"
import { PageHeader, ErrorBlock, SkeletonTable, RefModal } from "./_shared"
import type { Kollekciya } from "@/types/catalog"

const COLUMNS: TableColumn<Kollekciya>[] = [
  { key: "id",       label: "ID",        mono: true, dim: true },
  { key: "nazvanie", label: "Название" },
]

export function KollekciiPage() {
  const [modalOpen, setModalOpen] = useState(false)
  const qc = useQueryClient()
  const { data = [], isLoading, error } = useReference("kollekcii", fetchKollekcii)

  const handleAdd = async (values: Record<string, string>) => {
    await insertKollekciya({ nazvanie: values.nazvanie })
    await qc.invalidateQueries({ queryKey: ["catalog", "reference", "kollekcii"] })
  }

  return (
    <div className="px-6 py-6 max-w-4xl">
      <div className="flex items-center justify-between mb-4">
        <PageHeader title="Коллекции" count={data.length} isLoading={isLoading} />
        <button
          onClick={() => setModalOpen(true)}
          className="px-3 py-1.5 text-xs text-white bg-stone-900 hover:bg-stone-800 rounded-md flex items-center gap-1.5"
        >
          <Plus className="w-3.5 h-3.5" /> Добавить
        </button>
      </div>
      {error && <ErrorBlock message={error.message} />}
      {isLoading ? (
        <SkeletonTable rows={5} cols={2} />
      ) : (
        <CatalogTable columns={COLUMNS} data={data} emptyText="Коллекции не найдены" />
      )}
      {modalOpen && (
        <RefModal
          title="Новая коллекция"
          fields={[{ key: "nazvanie", label: "Название", placeholder: "Например: Трикотажное белье" }]}
          onSave={handleAdd}
          onClose={() => setModalOpen(false)}
        />
      )}
    </div>
  )
}
