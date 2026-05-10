import { PageHeader } from "@/components/crm/layout/PageHeader"
import { SearchQueriesTable } from "./search-queries/SearchQueriesTable"

export function SearchQueriesPage() {
  return (
    <div className="flex flex-col h-full">
      <div className="px-6 pt-6 pb-0">
        <PageHeader title="Поисковые запросы" sub="Брендовые, артикулы и подменные WW-коды" />
      </div>
      <SearchQueriesTable />
    </div>
  )
}
