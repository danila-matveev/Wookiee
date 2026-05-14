import { Outlet } from "react-router-dom"

export function MarketingLayout() {
  return (
    <div data-section="marketing" className="flex h-screen overflow-hidden" style={{ fontFamily: "'DM Sans', system-ui, sans-serif" }}>
      <main className="flex-1 flex flex-col overflow-hidden min-w-0">
        <Outlet />
      </main>
    </div>
  )
}
