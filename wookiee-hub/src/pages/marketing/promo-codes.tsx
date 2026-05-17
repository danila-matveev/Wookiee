import { useSearchParams } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { PageHeader } from "@/components/layout/page-header"
import { useDocumentTitle } from "@/hooks/use-document-title"
import { PromoCodesTable } from "./promo-codes/PromoCodesTable"
import { AddPromoPanel } from "./promo-codes/AddPromoPanel"
import { PromoDetailPanel } from "./promo-codes/PromoDetailPanel"

type ActivePanel =
  | { kind: 'add' }
  | { kind: 'detail'; promoId: number }
  | null

export function PromoCodesPage() {
  useDocumentTitle("Промокоды")
  const [params, setParams] = useSearchParams()
  const adding   = params.get('add') === '1'
  const openRaw  = params.get('open')
  const openId   = openRaw ? Number(openRaw) : null
  const detailId = openId != null && Number.isFinite(openId) && openId > 0 ? openId : null

  const openAdd     = () => setParams((p) => { p.set('add', '1'); return p })
  const closeAdd    = () => setParams((p) => { p.delete('add');  return p })
  const closeDetail = () => setParams((p) => { p.delete('open'); return p })

  const active: ActivePanel =
    adding              ? { kind: 'add' } :
    detailId != null    ? { kind: 'detail', promoId: detailId } :
    null

  const renderPanel = () => {
    if (!active) return null
    if (active.kind === 'add') return <AddPromoPanel onClose={closeAdd} />
    return <PromoDetailPanel promoId={active.promoId} onClose={closeDetail} />
  }

  return (
    <div className="flex flex-1 overflow-hidden">
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        <div className="px-6 pt-6 pb-0">
          <PageHeader
            kicker="МАРКЕТИНГ"
            title="Промокоды"
            description="Статистика по кодам скидок"
            breadcrumbs={[
              { label: "Маркетинг", to: "/marketing" },
              { label: "Промокоды", to: "/marketing/promo-codes" },
            ]}
            actions={<Button onClick={openAdd}>+ Добавить</Button>}
          />
        </div>
        <PromoCodesTable />
      </div>

      {renderPanel()}
    </div>
  )
}
