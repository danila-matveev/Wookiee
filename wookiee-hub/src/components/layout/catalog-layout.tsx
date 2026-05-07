import { useCallback, useEffect, useState } from "react"
import { Outlet, useSearchParams } from "react-router-dom"
import { CatalogSidebar } from "@/components/catalog/layout/catalog-sidebar"
import { CatalogTopBar } from "@/components/catalog/layout/catalog-topbar"
import { CommandPalette } from "@/components/catalog/ui/command-palette"

export function CatalogLayout() {
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [searchParams, setSearchParams] = useSearchParams()

  const closePalette = useCallback(() => setPaletteOpen(false), [])
  const openPalette = useCallback(() => setPaletteOpen(true), [])

  // Global hotkeys: ⌘K opens palette, Esc closes palette + clears ?model/?color modals
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault()
        setPaletteOpen((open) => !open)
        return
      }
      if (e.key === "Escape") {
        // Esc priority: close palette first; if not open, close model/color modal.
        if (paletteOpen) {
          setPaletteOpen(false)
          return
        }
        if (searchParams.get("model") || searchParams.get("color")) {
          const next = new URLSearchParams(searchParams)
          next.delete("model")
          next.delete("color")
          setSearchParams(next, { replace: true })
        }
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [paletteOpen, searchParams, setSearchParams])

  return (
    <div
      className="catalog-scope h-screen w-screen flex overflow-hidden"
      style={{ background: "rgb(250 250 249)" }}
    >
      <CatalogSidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <CatalogTopBar onOpenSearch={openPalette} />
        <main className="flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
      <CommandPalette open={paletteOpen} onClose={closePalette} />
    </div>
  )
}
