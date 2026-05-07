import { useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { Plus } from "lucide-react"
import { CatalogTable, type TableColumn } from "@/components/catalog/layout/catalog-table"
import { useReference } from "./_use-reference"
import { fetchRazmery, insertRazmer } from "@/lib/catalog/service"
import { PageHeader, ErrorBlock, SkeletonTable, RefModal } from "./_shared"
import type { Razmer } from "@/types/catalog"

const COLUMNS: TableColumn<Razmer>[] = [
  { key: "poryadok", label: "#",      mono: true, dim: true },
  { key: "nazvanie", label: "Размер" },
  { key: "id",       label: "ID",    mono: true, dim: true },
]

export function RazmeryPage() {
  const [modalOpen, setModalOpen] = useState(false)
  const qc = useQueryClient()
  const { data = [], isLoading, error } = useReference("razmery", fetchRazmery)

  const handleAdd = async (values: Record<string, string>) => {
    await insertRazmer({
      nazvanie: values.nazvanie,
      poryadok: Number(values.poryadok),
    })
    await qc.invalidateQueries({ queryKey: ["catalog", "reference", "razmery"] })
  }

  return (
    <div className="px-6 py-6 max-w-4xl">
      <div className="flex items-center justify-between mb-4">
        <PageHeader title="Размеры" count={data.length} isLoading={isLoading} />
        <button
          onClick={() => setModalOpen(true)}
          className="px-3 py-1.5 text-xs text-white bg-stone-900 hover:bg-stone-800 rounded-md flex items-center gap-1.5"
        >
          <Plus className="w-3.5 h-3.5" /> Добавить
        </button>
      </div>
      {error && <ErrorBlock message={error.message} />}
      {isLoading ? (
        <SkeletonTable rows={6} cols={3} />
      ) : (
        <CatalogTable columns={COLUMNS} data={data} emptyText="Размеры не найдены" />
      )}
      {modalOpen && (
        <RefModal
          title="Новый размер"
          fields={[
            { key: "nazvanie", label: "Размер", placeholder: "XS" },
            { key: "poryadok", label: "Порядок", type: "number" },
          ]}
          onSave={handleAdd}
          onClose={() => setModalOpen(false)}
        />
      )}
    </div>
  )
}
