import { useState } from "react"
import { CatalogHeader } from "@/components/catalog/catalog-header"
import { CatalogTable } from "@/components/catalog/catalog-table"
import { CatalogGrid } from "@/components/catalog/catalog-grid"
import { catalogModels, catalogCollections } from "@/data/catalog-mock"

export function CatalogPage() {
  const [viewMode, setViewMode] = useState("table")
  const [selectedCollection, setSelectedCollection] = useState("")

  const filteredModels = selectedCollection
    ? catalogModels.filter((m) => m.collection === selectedCollection)
    : catalogModels

  return (
    <div className="space-y-4">
      <CatalogHeader
        viewMode={viewMode}
        onViewChange={setViewMode}
        selectedCollection={selectedCollection}
        onCollectionChange={setSelectedCollection}
        collections={catalogCollections}
      />
      {viewMode === "table" ? (
        <CatalogTable models={filteredModels} />
      ) : (
        <CatalogGrid models={filteredModels} />
      )}
    </div>
  )
}
