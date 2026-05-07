import { useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { Plus } from "lucide-react"
import { CatalogTable, type TableColumn } from "@/components/catalog/layout/catalog-table"
import { useReference } from "./_use-reference"
import { fetchImportery, insertImporter } from "@/lib/catalog/service"
import { PageHeader, ErrorBlock, SkeletonTable, RefModal } from "./_shared"
import type { Importer } from "@/types/catalog"

const COLUMNS: TableColumn<Importer>[] = [
  { key: "id",          label: "ID",   mono: true, dim: true },
  { key: "nazvanie",    label: "Название" },
  { key: "nazvanie_en", label: "EN",   dim: true },
  { key: "inn",         label: "ИНН",  mono: true, dim: true },
]

export function ImporteryPage() {
  const [modalOpen, setModalOpen] = useState(false)
  const qc = useQueryClient()
  const { data = [], isLoading, error } = useReference("importery", fetchImportery)

  const handleAdd = async (values: Record<string, string>) => {
    await insertImporter({
      nazvanie: values.nazvanie,
      nazvanie_en: values.nazvanie_en || undefined,
      inn: values.inn || undefined,
      adres: values.adres || undefined,
    })
    await qc.invalidateQueries({ queryKey: ["catalog", "reference", "importery"] })
  }

  return (
    <div className="px-6 py-6 max-w-4xl">
      <div className="flex items-center justify-between mb-4">
        <PageHeader title="Юридические лица" count={data.length} isLoading={isLoading} />
        <button
          onClick={() => setModalOpen(true)}
          className="px-3 py-1.5 text-xs text-white bg-stone-900 hover:bg-stone-800 rounded-md flex items-center gap-1.5"
        >
          <Plus className="w-3.5 h-3.5" /> Добавить
        </button>
      </div>
      {error && <ErrorBlock message={error.message} />}
      {isLoading ? (
        <SkeletonTable rows={3} cols={4} />
      ) : (
        <CatalogTable columns={COLUMNS} data={data} emptyText="Импортёры не найдены" />
      )}
      {modalOpen && (
        <RefModal
          title="Новое юридическое лицо"
          fields={[
            { key: "nazvanie", label: "Название (полное)" },
            { key: "nazvanie_en", label: "Название EN" },
            { key: "inn", label: "ИНН" },
            { key: "adres", label: "Адрес" },
          ]}
          onSave={handleAdd}
          onClose={() => setModalOpen(false)}
        />
      )}
    </div>
  )
}
