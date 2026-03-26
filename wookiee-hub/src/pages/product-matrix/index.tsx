import { MatrixSidebar } from "@/components/matrix/matrix-sidebar"
import { DetailPanel } from "@/components/matrix/detail-panel"
import { GlobalSearch } from "@/components/matrix/global-search"
import { MassEditBar } from "@/components/matrix/mass-edit-bar"
import { useMatrixStore } from "@/stores/matrix-store"
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
  const Page = ENTITY_PAGES[activeEntity]

  return (
    <div className="flex h-full">
      <MatrixSidebar />
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
