import { useSearchParams } from "react-router-dom"
import { Button } from "@/components/crm/ui/Button"
import { useMediaQuery } from "@/hooks/use-media-query"
import { PromoCodesTable } from "./promo-codes/PromoCodesTable"
import { AddPromoPanel } from "./promo-codes/AddPromoPanel"
import { PromoDetailPanel } from "./promo-codes/PromoDetailPanel"

type ActivePanel =
  | { kind: 'add' }
  | { kind: 'detail'; promoId: number }
  | null

export function PromoCodesPage() {
  const [params, setParams] = useSearchParams()
  const adding   = params.get('add') === '1'
  const openRaw  = params.get('open')
  const openId   = openRaw ? Number(openRaw) : null
  const detailId = openId != null && Number.isFinite(openId) && openId > 0 ? openId : null
  const isWide   = useMediaQuery('(min-width: 1024px)')

  const openAdd     = () => setParams((p) => { p.set('add', '1'); return p })
  const closeAdd    = () => setParams((p) => { p.delete('add');  return p })
  const closeDetail = () => setParams((p) => { p.delete('open'); return p })

  // Add takes precedence over detail when both URL params are set (user just clicked Add).
  const active: ActivePanel =
    adding              ? { kind: 'add' } :
    detailId != null    ? { kind: 'detail', promoId: detailId } :
    null

  // Add forms always use modal Drawer (sticky footer with Save button reliably visible regardless
  // of parent height cascade). Detail panels use split-pane on wide screens for context preservation.
  const renderPanel = (mode: 'drawer' | 'inline') => {
    if (!active) return null
    if (active.kind === 'add') return <AddPromoPanel onClose={closeAdd} mode="drawer" />
    return <PromoDetailPanel promoId={active.promoId} onClose={closeDetail} mode={mode} />
  }

  return (
    <div className="flex flex-1 overflow-hidden">
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
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
            <Button variant="primary" onClick={openAdd}>
              + Добавить
            </Button>
          </div>
        </div>
        <PromoCodesTable />
      </div>

      {/* Detail = split-pane on lg+ (preserves table context). Add = always Drawer modal. */}
      {active?.kind === 'add' && renderPanel('drawer')}
      {active?.kind === 'detail' && isWide && (
        <aside className="w-[560px] shrink-0 border-l border-border bg-card flex flex-col h-full overflow-hidden">
          {renderPanel('inline')}
        </aside>
      )}
      {active?.kind === 'detail' && !isWide && renderPanel('drawer')}
    </div>
  )
}
