import { useSearchParams } from "react-router-dom"
import { PageHeader } from "@/components/crm/layout/PageHeader"
import { Button } from "@/components/crm/ui/Button"
import { PromoCodesTable } from "./promo-codes/PromoCodesTable"
import { AddPromoPanel } from "./promo-codes/AddPromoPanel"

export function PromoCodesPage() {
  const [params, setParams] = useSearchParams()
  const adding = params.get('add') === '1'

  return (
    <div className="flex flex-col h-full">
      <div className="px-6 pt-6 pb-0">
        <PageHeader
          title="Промокоды"
          sub="Статистика по кодам скидок"
          actions={
            <Button
              variant="primary"
              onClick={() => setParams((p) => { p.set('add', '1'); return p })}
            >
              + Добавить
            </Button>
          }
        />
      </div>
      <PromoCodesTable />
      {adding && (
        <AddPromoPanel onClose={() => setParams((p) => { p.delete('add'); return p })} />
      )}
    </div>
  )
}
