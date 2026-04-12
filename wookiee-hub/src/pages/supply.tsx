// ---------------------------------------------------------------------------
// Supply Planning — main page
// ---------------------------------------------------------------------------

import { useState } from "react"
import { useSupplyStore } from "@/stores/supply"
import { SupplyHeader } from "@/components/supply/supply-header"
import { SupplyProductTable } from "@/components/supply/supply-product-table"
import { SupplyAlertsList } from "@/components/supply/supply-alerts-list"
import { SupplyTimeline } from "@/components/supply/supply-timeline"
import { SupplyOrderForm } from "@/components/supply/supply-order-form"
import { SupplySettingsPanel } from "@/components/supply/supply-settings-panel"

function SupplyPage() {
  const viewMode = useSupplyStore((s) => s.viewMode)
  const settingsOpen = useSupplyStore((s) => s.settingsOpen)
  const setSettingsOpen = useSupplyStore((s) => s.setSettingsOpen)
  const [orderFormOpen, setOrderFormOpen] = useState(false)

  return (
    <div className="flex flex-col gap-4 p-4">
      <SupplyHeader onNewOrder={() => setOrderFormOpen(true)} />

      {viewMode === "table" && <SupplyProductTable />}
      {viewMode === "timeline" && <SupplyTimeline />}
      {viewMode === "alerts" && <SupplyAlertsList />}

      <SupplyOrderForm
        open={orderFormOpen}
        onOpenChange={setOrderFormOpen}
      />

      <SupplySettingsPanel
        open={settingsOpen}
        onOpenChange={setSettingsOpen}
      />
    </div>
  )
}

export { SupplyPage }
