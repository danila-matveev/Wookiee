import { Outlet } from "react-router-dom"
import { CatalogSidebar } from "@/components/catalog/layout/catalog-sidebar"
import { CatalogTopBar } from "@/components/catalog/layout/catalog-topbar"

export function CatalogLayout() {
  return (
    <div className="catalog-scope h-screen w-screen flex overflow-hidden" style={{ background: 'rgb(250 250 249)' }}>
      <CatalogSidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <CatalogTopBar />
        <main className="flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
