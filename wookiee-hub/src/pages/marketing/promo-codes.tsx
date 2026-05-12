import { useSearchParams } from "react-router-dom"
import { Button } from "@/components/crm/ui/Button"
import { PromoCodesTable } from "./promo-codes/PromoCodesTable"
import { AddPromoPanel } from "./promo-codes/AddPromoPanel"

export function PromoCodesPage() {
  const [params, setParams] = useSearchParams()
  const adding = params.get('add') === '1'

  return (
    <div className="flex flex-col h-full">
      <div className="px-6 pt-6 pb-0">
        <div className="flex items-end justify-between mb-6">
          <div>
            <h1
              className="text-stone-900"
              style={{ fontFamily: "'Instrument Serif', serif", fontSize: 24, fontStyle: "italic" }}
            >
              Промокоды
            </h1>
            <p className="text-sm text-stone-500 mt-0.5">Статистика по кодам скидок</p>
          </div>
          <Button
            variant="primary"
            onClick={() => setParams((p) => { p.set('add', '1'); return p })}
          >
            + Добавить
          </Button>
        </div>
      </div>
      <PromoCodesTable />
      {adding && (
        <AddPromoPanel onClose={() => setParams((p) => { p.delete('add'); return p })} />
      )}
    </div>
  )
}
