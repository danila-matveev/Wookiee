import { useApiQuery } from "@/hooks/use-api-query"
import { matrixApi, type Sertifikat } from "@/lib/matrix-api"
import { useMatrixStore } from "@/stores/matrix-store"
import { DataTable, type Column } from "@/components/matrix/data-table"
import { ViewTabs } from "@/components/matrix/view-tabs"
import { MatrixTopbar } from "@/components/matrix/matrix-topbar"

const columns: Column<Sertifikat>[] = [
  { key: "nazvanie", label: "Название", width: 200, type: "text" },
  { key: "tip", label: "Тип", width: 160, type: "text" },
  { key: "nomer", label: "Номер", width: 140, type: "text" },
  { key: "data_vydachi", label: "Дата выдачи", width: 120, type: "readonly" },
  { key: "data_okonchaniya", label: "Окончание", width: 120, type: "readonly" },
  { key: "organ_sertifikacii", label: "Орган", width: 200, type: "text" },
  { key: "gruppa_sertifikata", label: "Группа", width: 120, type: "text" },
]

export function CertsPage() {
  const selectedRows = useMatrixStore((s) => s.selectedRows)
  const toggleRowSelected = useMatrixStore((s) => s.toggleRowSelected)
  const openDetailPanel = useMatrixStore((s) => s.openDetailPanel)
  const entityUpdateStamp = useMatrixStore((s) => s.entityUpdateStamp["certs"] ?? 0)

  const { data, loading } = useApiQuery(
    () => matrixApi.listCerts({ per_page: 200 }),
    [entityUpdateStamp],
  )

  return (
    <div className="space-y-0">
      <MatrixTopbar />
      <ViewTabs />
      <DataTable
        columns={columns}
        data={data?.items ?? []}
        loading={loading}
        selectedRows={selectedRows}
        onToggleSelect={toggleRowSelected}
        onRowClick={(id) => openDetailPanel(id, "certs")}
      />
    </div>
  )
}
