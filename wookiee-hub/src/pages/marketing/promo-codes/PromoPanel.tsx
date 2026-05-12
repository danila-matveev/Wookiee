import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react"
import { Edit3 } from "lucide-react"
import { InlinePanel } from "@/components/marketing/InlinePanel"
import { SelectMenu } from "@/components/marketing/SelectMenu"
import { Badge } from "@/components/crm/ui/Badge"
import { Input } from "@/components/crm/ui/Input"
import { Button } from "@/components/crm/ui/Button"
import { EmptyState } from "@/components/crm/ui/EmptyState"
import {
  useCreatePromoCode,
  usePromoCodes,
  usePromoProductBreakdown,
  usePromoStatsForCode,
  useUpdatePromoCode,
} from "@/hooks/marketing/use-promo-codes"
import { useChannels } from "@/hooks/marketing/use-channels"
import { derivePromoStatus, formatWeekShort } from "@/lib/marketing-helpers"
import type {
  PromoCodeRow,
  PromoProductBreakdownRow,
  PromoProductTotal,
  PromoStatWeekly,
} from "@/types/marketing"

export type PromoPanelMode = "add" | "view" | "edit"

interface PromoPanelProps {
  mode: PromoPanelMode
  promoId: number | null
  onClose: () => void
  onModeChange?: (mode: PromoPanelMode) => void
}

const lCls = "block text-[11px] uppercase tracking-wider text-muted-foreground font-medium mb-1"
const fmt  = (n: number) => n.toLocaleString("ru-RU")
const fmtR = (n: number) => `${n.toLocaleString("ru-RU")} ₽`

interface FormState {
  code: string
  channel: string
  discount: string
  from: string
  until: string
}

function emptyForm(): FormState {
  return { code: "", channel: "", discount: "", from: "", until: "" }
}

function formFromPromo(p: PromoCodeRow): FormState {
  return {
    code: p.code,
    channel: p.channel ?? "",
    discount: p.discount_pct != null ? String(p.discount_pct) : "",
    from: p.valid_from ?? "",
    until: p.valid_until ?? "",
  }
}

export function PromoPanel({ mode, promoId, onClose, onModeChange }: PromoPanelProps) {
  const isAdd  = mode === "add"
  const isEdit = mode === "edit"
  const editing = isAdd || isEdit

  const { data: promos = [], isLoading: lp } = usePromoCodes()
  const { data: channels = [] } = useChannels()
  const create = useCreatePromoCode()
  const update = useUpdatePromoCode()

  const promo: PromoCodeRow | undefined = isAdd
    ? undefined
    : promos.find((p) => p.id === promoId)

  const { data: weekly = [], isLoading: lw } = usePromoStatsForCode(isAdd ? null : promoId)
  const { data: breakdown = [], isLoading: lb } = usePromoProductBreakdown(isAdd ? null : promoId)

  const [form, setForm] = useState<FormState>(emptyForm)
  const [error, setError] = useState<string | null>(null)

  // Sync form state when promo data arrives, the row identity changes, or the mode flips.
  // Without this, useState's once-only initializer leaves the form empty if `promo` is still
  // loading at mount time (mode='view' → 'edit' from URL, or first paint before query resolves).
  useEffect(() => {
    if (isAdd) {
      setForm(emptyForm())
      return
    }
    if (promo) setForm(formFromPromo(promo))
  }, [isAdd, mode, promo?.id, promo?.updated_at])

  // crm.promo_codes.channel stores the human-readable label (e.g. "Блогер"), not the slug —
  // so the picker must round-trip on label, otherwise existing rows render as "unknown channel".
  const channelOptions = useMemo(
    () => channels.map((c) => ({ value: c.label, label: c.label })),
    [channels],
  )

  const channelKnown = useMemo(() => {
    if (!form.channel) return true
    return channelOptions.some((o) => o.value === form.channel)
  }, [form.channel, channelOptions])

  const totals = useMemo(() => sumWeekly(weekly), [weekly])
  const products = useMemo(() => aggregateProducts(breakdown), [breakdown])

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)

    if (!form.code.trim()) {
      setError("Код промокода обязателен")
      return
    }

    const discount = form.discount.trim() === "" ? null : Number(form.discount)
    if (discount != null && (Number.isNaN(discount) || discount < 0 || discount > 100)) {
      setError("Скидка должна быть числом от 0 до 100")
      return
    }

    try {
      if (isAdd) {
        await create.mutateAsync({
          code: form.code,
          channel: form.channel || undefined,
          discount_pct: discount ?? undefined,
          valid_from: form.from || undefined,
          valid_until: form.until || undefined,
        })
        onClose()
      } else if (promo) {
        await update.mutateAsync({
          id: promo.id,
          patch: {
            code: form.code,
            channel: form.channel || null,
            discount_pct: discount,
            valid_from: form.from || null,
            valid_until: form.until || null,
          },
        })
        onModeChange?.("view")
      }
    } catch (err) {
      if (err && typeof err === "object" && "code" in err && (err as { code?: string }).code === "23505") {
        setError("Промокод с таким кодом уже существует")
      } else {
        setError(err instanceof Error ? err.message : "Не удалось сохранить промокод")
      }
    }
  }

  const handleCancelEdit = () => {
    if (promo) setForm(formFromPromo(promo))
    setError(null)
    onModeChange?.("view")
  }

  // Header — either "Новый промокод" or mono code + status badge + channel badge + edit button
  const header: ReactNode = isAdd ? (
    <div className="text-sm font-medium text-foreground">Новый промокод</div>
  ) : promo ? (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center gap-2">
        <div className="font-mono text-xs text-muted-foreground break-all flex-1 min-w-0">{promo.code}</div>
        {!isEdit && (
          <button
            type="button"
            aria-label="Редактировать"
            onClick={() => onModeChange?.("edit")}
            className="p-1.5 rounded-md text-muted-foreground hover:bg-muted shrink-0"
          >
            <Edit3 className="w-3.5 h-3.5" aria-hidden />
          </button>
        )}
      </div>
      <div className="flex items-center gap-1.5 flex-wrap">
        <PromoStatusBadge promo={promo} qty={totals.qty} />
        {promo.channel && <Badge tone="secondary">{promo.channel}</Badge>}
      </div>
    </div>
  ) : (
    <div className="text-sm text-muted-foreground">Промокод</div>
  )

  return (
    <InlinePanel title={header} onClose={onClose} width={400}>
      {!isAdd && lp ? (
        <div className="px-5 py-4 text-sm text-muted-foreground">Загрузка…</div>
      ) : !isAdd && !promo ? (
        <div className="px-5 py-4">
          <EmptyState title="Промокод не найден" description="Возможно, он удалён или ID неверен." />
        </div>
      ) : (
        <>
          <form onSubmit={handleSubmit} className="px-5 py-4 border-b border-border space-y-3">
            <div>
              <label className={lCls} htmlFor="promo-code-input">Код</label>
              {editing ? (
                <Input
                  id="promo-code-input"
                  value={form.code}
                  onChange={(e) => setForm((f) => ({ ...f, code: e.target.value }))}
                  className="font-mono uppercase"
                  autoFocus={isAdd}
                  autoComplete="off"
                  placeholder="SUMMER20"
                />
              ) : (
                <div className="font-mono text-xs text-foreground break-all">{form.code}</div>
              )}
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                {editing ? (
                  <SelectMenu
                    label="Канал"
                    value={form.channel}
                    options={channelOptions}
                    onChange={(v) => setForm((f) => ({ ...f, channel: v }))}
                    allowAdd
                    placeholder="Выбрать…"
                    newValueLabel="Добавить канал"
                  />
                ) : (
                  <div>
                    <div className={lCls}>Канал</div>
                    <div className="text-sm text-foreground">{form.channel || "—"}</div>
                  </div>
                )}
                {editing && form.channel && !channelKnown && (
                  <p className="text-[10px] text-muted-foreground mt-1">
                    Сначала добавьте канал в справочник.
                  </p>
                )}
              </div>
              <div>
                <label className={lCls} htmlFor="promo-discount-input">Скидка %</label>
                {editing ? (
                  <Input
                    id="promo-discount-input"
                    type="number"
                    min={0}
                    max={100}
                    step={0.01}
                    value={form.discount}
                    onChange={(e) => setForm((f) => ({ ...f, discount: e.target.value }))}
                    placeholder="20"
                  />
                ) : (
                  <div className="text-sm tabular-nums text-foreground">
                    {form.discount ? `${form.discount}%` : "—"}
                  </div>
                )}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className={lCls} htmlFor="promo-from-input">Начало</label>
                {editing ? (
                  <Input
                    id="promo-from-input"
                    type="date"
                    value={form.from}
                    onChange={(e) => setForm((f) => ({ ...f, from: e.target.value }))}
                  />
                ) : (
                  <div className="text-sm tabular-nums text-foreground">{form.from || "—"}</div>
                )}
              </div>
              <div>
                <label className={lCls} htmlFor="promo-until-input">Окончание</label>
                {editing ? (
                  <Input
                    id="promo-until-input"
                    type="date"
                    value={form.until}
                    min={form.from || undefined}
                    onChange={(e) => setForm((f) => ({ ...f, until: e.target.value }))}
                  />
                ) : (
                  <div className="text-sm tabular-nums text-foreground">{form.until || "—"}</div>
                )}
              </div>
            </div>

            {editing && (
              <div className="flex gap-2 pt-1">
                <Button
                  variant="primary"
                  type="submit"
                  loading={isAdd ? create.isPending : update.isPending}
                  className="flex-1 justify-center"
                >
                  {isAdd ? "Создать" : "Сохранить"}
                </Button>
                {isEdit && (
                  <Button
                    variant="secondary"
                    type="button"
                    onClick={handleCancelEdit}
                    disabled={update.isPending}
                  >
                    Отмена
                  </Button>
                )}
              </div>
            )}

            {error && <p className="text-xs text-danger" role="alert">{error}</p>}
          </form>

          {!isAdd && promo && (
            <>
              <div className="px-5 py-4 border-b border-border">
                <div className="grid grid-cols-3 gap-3">
                  <KpiBlock label="Продажи, шт" value={fmt(totals.qty)} />
                  <KpiBlock label="Продажи, ₽" value={fmtR(totals.sales)} />
                  <KpiBlock
                    label="Ср. чек, ₽"
                    value={totals.qty > 0 ? fmtR(Math.round(totals.sales / totals.qty)) : "—"}
                  />
                </div>
              </div>

              <ProductBreakdownSection products={products} loading={lb} />
              <WeeklySection weekly={weekly} loading={lw} />
            </>
          )}
        </>
      )}
    </InlinePanel>
  )
}

interface KpiBlockProps {
  label: string
  value: string
}

function KpiBlock({ label, value }: KpiBlockProps) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-wider text-muted-foreground font-medium mb-0.5">
        {label}
      </div>
      <div className="text-lg font-medium text-foreground tabular-nums">{value}</div>
    </div>
  )
}

interface PromoStatusBadgeProps {
  promo: PromoCodeRow
  qty: number
}

function PromoStatusBadge({ promo, qty }: PromoStatusBadgeProps) {
  const s = derivePromoStatus({ status: promo.status, qty, channel: promo.channel })
  return <Badge tone={s.tone}>{s.label}</Badge>
}

interface ProductBreakdownSectionProps {
  products: PromoProductTotal[]
  loading: boolean
}

function ProductBreakdownSection({ products, loading }: ProductBreakdownSectionProps) {
  return (
    <div className="px-5 py-4 border-b border-border">
      <div className="text-[11px] uppercase tracking-wider text-muted-foreground font-medium mb-2">
        Товарная разбивка
      </div>
      {loading ? (
        <div className="text-xs text-muted-foreground">Загрузка…</div>
      ) : products.length === 0 ? (
        <EmptyState title="Товарная разбивка" description="Данные появятся после первого выкупа." />
      ) : (
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-border/60">
              <th className="text-left  py-1 text-[10px] uppercase text-muted-foreground font-medium">Товар</th>
              <th className="text-right py-1 text-[10px] uppercase text-muted-foreground font-medium">Шт</th>
              <th className="text-right py-1 text-[10px] uppercase text-muted-foreground font-medium">Сумма</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/40">
            {products.map((p) => (
              <tr key={p.sku_label}>
                <td className="py-1.5">
                  <div className="text-foreground">{p.sku_label}</div>
                  {p.model_code && (
                    <div className="text-[10px] text-muted-foreground">{p.model_code}</div>
                  )}
                </td>
                <td className="py-1.5 text-right tabular-nums text-foreground/80">{p.qty}</td>
                <td className="py-1.5 text-right tabular-nums text-foreground font-medium">{fmtR(p.amount_rub)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

interface WeeklySectionProps {
  weekly: PromoStatWeekly[]
  loading: boolean
}

function WeeklySection({ weekly, loading }: WeeklySectionProps) {
  return (
    <div className="px-5 py-4">
      <div className="text-[11px] uppercase tracking-wider text-muted-foreground font-medium mb-2">
        По неделям
      </div>
      {loading ? (
        <div className="text-xs text-muted-foreground">Загрузка…</div>
      ) : weekly.length === 0 ? (
        <EmptyState title="По неделям" description="Данные появятся после понедельника." />
      ) : (
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-border/60">
              <th className="text-left  py-1 text-[10px] uppercase text-muted-foreground font-medium">Нед</th>
              <th className="text-right py-1 text-[10px] uppercase text-muted-foreground font-medium">Зак</th>
              <th className="text-right py-1 text-[10px] uppercase text-muted-foreground font-medium">Продажи</th>
              <th className="text-right py-1 text-[10px] uppercase text-muted-foreground font-medium">Возвр</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/40">
            {weekly.map((w) => (
              <tr key={w.week_start}>
                <td className="py-1.5 tabular-nums text-muted-foreground">{formatWeekShort(w.week_start)}</td>
                <td className="py-1.5 text-right tabular-nums text-foreground font-medium">{w.orders_count}</td>
                <td className="py-1.5 text-right tabular-nums text-foreground/80">{fmtR(w.sales_rub)}</td>
                <td className="py-1.5 text-right tabular-nums text-muted-foreground">{w.returns_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

function sumWeekly(rows: PromoStatWeekly[]): { qty: number; sales: number } {
  let qty = 0
  let sales = 0
  for (const r of rows) {
    qty   += r.orders_count
    sales += r.sales_rub
  }
  return { qty, sales }
}

function aggregateProducts(rows: PromoProductBreakdownRow[]): PromoProductTotal[] {
  const map = new Map<string, PromoProductTotal>()
  for (const r of rows) {
    const cur = map.get(r.sku_label) ?? {
      sku_label:  r.sku_label,
      model_code: r.model_code,
      qty: 0,
      amount_rub: 0,
    }
    cur.qty        += r.qty
    cur.amount_rub += r.amount_rub
    if (!cur.model_code && r.model_code) cur.model_code = r.model_code
    map.set(r.sku_label, cur)
  }
  return Array.from(map.values()).sort((a, b) => b.amount_rub - a.amount_rub)
}
