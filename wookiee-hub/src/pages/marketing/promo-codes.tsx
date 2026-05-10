import { PageHeader } from "@/components/crm/layout/PageHeader"
import { PromoCodesTable } from "./promo-codes/PromoCodesTable"

export function PromoCodesPage() {
  return (
    <div className="flex flex-col h-full">
      <div className="px-6 pt-6 pb-0">
        <PageHeader title="Промокоды" sub="Статистика по кодам скидок" />
      </div>
      <PromoCodesTable />
    </div>
  )
}
