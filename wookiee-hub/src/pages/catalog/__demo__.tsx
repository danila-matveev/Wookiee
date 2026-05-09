// Wire-up to the real atomic UI demo from A3 (lives in components/catalog/ui/__demo__.tsx).
// Page-level wrapper exposes `DemoPage` for router.tsx.

import CatalogUiDemo from "@/components/catalog/ui/__demo__"

export function DemoPage() {
  return <CatalogUiDemo />
}
