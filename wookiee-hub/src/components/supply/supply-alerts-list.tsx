// ---------------------------------------------------------------------------
// Supply Alerts List — shows products with low stock, grouped by severity
// ---------------------------------------------------------------------------

import { useMemo } from "react"
import { useSupplyStore } from "@/stores/supply"
import { generateAlerts } from "@/lib/supply-calc"
import type { SupplyAlert } from "@/types/supply"
import { AlertTriangle, AlertCircle } from "lucide-react"

export function SupplyAlertsList() {
  const products = useSupplyStore((s) => s.products)
  const settings = useSupplyStore((s) => s.settings[s.entity])
  const getBlocks = useSupplyStore((s) => s.getBlocks)

  const alerts = useMemo(() => {
    const blocks = getBlocks()
    return generateAlerts(products, blocks, settings)
  }, [products, settings, getBlocks])

  const critical = useMemo(
    () => alerts.filter((a) => a.alert_level === "critical"),
    [alerts],
  )
  const warning = useMemo(
    () => alerts.filter((a) => a.alert_level === "warning"),
    [alerts],
  )

  if (alerts.length === 0) {
    return (
      <div className="flex items-center justify-center py-16 text-sm text-muted-foreground">
        Нет активных алертов — запасы в норме
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {critical.length > 0 && (
        <AlertSection
          title="КРИТИЧЕСКИЕ"
          alerts={critical}
          icon={<AlertCircle size={16} />}
          headerClass="text-red-600 dark:text-red-400"
          badgeBg="bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300"
        />
      )}

      {warning.length > 0 && (
        <AlertSection
          title="ПРЕДУПРЕЖДЕНИЯ"
          alerts={warning}
          icon={<AlertTriangle size={16} />}
          headerClass="text-amber-600 dark:text-amber-400"
          badgeBg="bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300"
        />
      )}
    </div>
  )
}

// ── Section ─────────────────────────────────────────────────────────────────

interface AlertSectionProps {
  title: string
  alerts: SupplyAlert[]
  icon: React.ReactNode
  headerClass: string
  badgeBg: string
}

function AlertSection({ title, alerts, icon, headerClass, badgeBg }: AlertSectionProps) {
  return (
    <div>
      {/* Section header */}
      <div className={`flex items-center gap-2 mb-3 text-sm font-semibold ${headerClass}`}>
        {icon}
        {title}
        <span className={`ml-1 inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ${badgeBg}`}>
          {alerts.length}
        </span>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/50">
              <th className="px-3 py-2 text-left font-medium text-muted-foreground">Артикул</th>
              <th className="px-3 py-2 text-left font-medium text-muted-foreground">Модель</th>
              <th className="px-3 py-2 text-left font-medium text-muted-foreground">Размер</th>
              <th className="px-3 py-2 text-right font-medium text-muted-foreground">Хватит дней</th>
              <th className="px-3 py-2 text-left font-medium text-muted-foreground">Закончится</th>
              <th className="px-3 py-2 text-left font-medium text-muted-foreground">Рекомендация</th>
            </tr>
          </thead>
          <tbody>
            {alerts.map((alert) => (
              <tr
                key={alert.product.barcode}
                className="border-b border-border last:border-b-0 hover:bg-muted/30 transition-colors"
              >
                <td className="px-3 py-2 font-mono text-xs">{alert.product.artikul}</td>
                <td className="px-3 py-2">{alert.product.model_name}</td>
                <td className="px-3 py-2">{alert.product.size}</td>
                <td className="px-3 py-2 text-right tabular-nums font-medium">
                  {alert.sufficient_days}
                </td>
                <td className="px-3 py-2 tabular-nums">{alert.sufficient_until}</td>
                <td className="px-3 py-2 text-muted-foreground">{alert.recommendation}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
