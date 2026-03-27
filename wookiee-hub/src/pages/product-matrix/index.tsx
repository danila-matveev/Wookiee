import { useEffect } from "react"
import { DetailPanel } from "@/components/matrix/detail-panel"
import { GlobalSearch } from "@/components/matrix/global-search"
import { MassEditBar } from "@/components/matrix/mass-edit-bar"
import { EntityTabs } from "@/components/matrix/entity-tabs"
import { useMatrixStore } from "@/stores/matrix-store"
import { useNavigationStore } from "@/stores/navigation"
import { ModelsPage } from "./models-page"
import { ArticlesPage } from "./articles-page"
import { ProductsPage } from "./products-page"
import { ColorsPage } from "./colors-page"
import { FactoriesPage } from "./factories-page"
import { ImportersPage } from "./importers-page"
import { CardsWBPage } from "./cards-wb-page"
import { CardsOzonPage } from "./cards-ozon-page"
import { CertsPage } from "./certs-page"

const ENTITY_PAGES = {
  models: ModelsPage,
  articles: ArticlesPage,
  products: ProductsPage,
  colors: ColorsPage,
  factories: FactoriesPage,
  importers: ImportersPage,
  "cards-wb": CardsWBPage,
  "cards-ozon": CardsOzonPage,
  certs: CertsPage,
} as const

export function ProductMatrixLayout() {
  const activeEntity = useMatrixStore((s) => s.activeEntity)
  const closeSidebar = useNavigationStore((s) => s.closeSidebar)
  const Page = ENTITY_PAGES[activeEntity]

  // Auto-close SubSidebar on matrix page — entity tabs replace it
  useEffect(() => { closeSidebar() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="flex flex-col h-full -m-4 sm:-m-6">
      {/* Entity tabs bar — replaces the old MatrixSidebar */}
      <div className="border-b border-border bg-muted/30 px-3 py-2">
        <EntityTabs />
      </div>
      {/* Main content */}
      <div className="flex flex-1 flex-col overflow-hidden">
        <main className="flex-1 overflow-auto">
          <Page />
        </main>
        <MassEditBar />
      </div>
      <DetailPanel />
      <GlobalSearch />
    </div>
  )
}
