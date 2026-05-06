import { useState } from "react"
import { ChevronDown, ChevronUp } from "lucide-react"

export function RnpHelpBlock() {
  const [open, setOpen] = useState(false)

  return (
    <div className="rounded-lg border bg-muted/30 px-4 py-3">
      <button
        className="flex w-full items-center justify-between text-sm font-medium"
        onClick={() => setOpen(!open)}
      >
        <span>РНП — Рука на пульсе: как читать дашборд</span>
        {open ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
      </button>
      {open && (
        <div className="mt-3 space-y-2 text-sm text-muted-foreground">
          <p>Дашборд показывает недельную динамику по выбранной модели. Данные обновляются ежедневно (T−1).</p>
          <p>
            <strong>Фазы недель:</strong>{" "}
            <span className="text-[#185FA5] font-medium">■ Норма</span> — маржа ≥ 15% &nbsp;
            <span className="text-[#1D9E75] font-medium">■ Восстановление</span> — 10–15% &nbsp;
            <span className="text-[#E24B4A] font-medium">■ Спад</span> — маржа &lt; 10%
          </p>
          <p>
            <strong>Выкуп %</strong> — лаговый показатель (3–21 дней). Последние недели занижены.
          </p>
          <p>
            <strong>Клики и корзина</strong> (воронка) — данные WB content_analysis, возможно расхождение ~20% с другими отчётами.
          </p>
          <p>
            <strong>Прогноз</strong> — считается на основе прогнозного выкупа (по умолчанию = фактический за период).
          </p>
          <p>Кликните по серии в легенде графика, чтобы скрыть/показать её.</p>
        </div>
      )}
    </div>
  )
}
