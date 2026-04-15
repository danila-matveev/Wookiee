// ---------------------------------------------------------------------------
// Supply Settings Panel — dialog for configuring per-entity supply parameters
// ---------------------------------------------------------------------------

import { useEffect, useState } from "react"
import { useSupplyStore } from "@/stores/supply"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import type { SupplySettings } from "@/types/supply"

interface SupplySettingsPanelProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

const FIELDS: {
  key: keyof Omit<SupplySettings, "entity">
  label: string
  step?: number
}[] = [
  { key: "default_return_rate", label: "% возвратов", step: 0.01 },
  { key: "target_coverage_days", label: "Целевое покрытие" },
  { key: "safety_stock_days", label: "Порог алерта warning" },
  { key: "critical_stock_days", label: "Порог алерта critical" },
  { key: "orders_window_days", label: "Окно расчёта заказов/день" },
  { key: "default_lead_time_days", label: "Lead time заказ→отправка" },
  { key: "default_transit_days", label: "Transit time отпр→дост" },
  { key: "default_offset_days", label: "Смещение по умолчанию" },
]

export function SupplySettingsPanel({
  open,
  onOpenChange,
}: SupplySettingsPanelProps) {
  const entity = useSupplyStore((s) => s.entity)
  const settings = useSupplyStore((s) => s.settings[s.entity])
  const updateSettings = useSupplyStore((s) => s.updateSettings)

  const [local, setLocal] = useState<Omit<SupplySettings, "entity">>(() => ({
    default_return_rate: settings.default_return_rate,
    target_coverage_days: settings.target_coverage_days,
    safety_stock_days: settings.safety_stock_days,
    critical_stock_days: settings.critical_stock_days,
    orders_window_days: settings.orders_window_days,
    default_lead_time_days: settings.default_lead_time_days,
    default_transit_days: settings.default_transit_days,
    default_offset_days: settings.default_offset_days,
  }))

  // Sync local state when the dialog opens or entity changes
  useEffect(() => {
    if (open) {
      setLocal({
        default_return_rate: settings.default_return_rate,
        target_coverage_days: settings.target_coverage_days,
        safety_stock_days: settings.safety_stock_days,
        critical_stock_days: settings.critical_stock_days,
        orders_window_days: settings.orders_window_days,
        default_lead_time_days: settings.default_lead_time_days,
        default_transit_days: settings.default_transit_days,
        default_offset_days: settings.default_offset_days,
      })
    }
  }, [open, settings])

  const handleChange = (key: keyof Omit<SupplySettings, "entity">, value: string) => {
    const parsed = Number(value)
    if (!Number.isNaN(parsed)) {
      setLocal((prev) => ({ ...prev, [key]: parsed }))
    }
  }

  const handleSave = () => {
    updateSettings(entity, local)
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>
            Настройки поставок — {entity === "ooo" ? "ООО" : "ИП"}
          </DialogTitle>
        </DialogHeader>

        <div className="grid gap-4 py-4">
          {FIELDS.map(({ key, label, step }) => (
            <div key={key} className="grid grid-cols-[1fr_100px] items-center gap-4">
              <Label htmlFor={key}>{label}</Label>
              <Input
                id={key}
                type="number"
                step={step ?? 1}
                value={local[key]}
                onChange={(e) => handleChange(key, e.target.value)}
              />
            </div>
          ))}
        </div>

        <DialogFooter>
          <Button onClick={handleSave}>Сохранить</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
