import { supabase } from '@/lib/supabase'
import type { PromoCodeRow, PromoStatWeekly, PromoProductBreakdownRow } from '@/types/marketing'
import { numToNumber } from '@/lib/marketing-helpers'

export interface PromoCreate {
  code: string
  name?: string
  external_uuid?: string
  channel?: string
  discount_pct?: number
  valid_from?: string
  valid_until?: string
}

export async function createPromoCode(input: PromoCreate): Promise<PromoCodeRow> {
  const { data, error } = await supabase.schema('crm').from('promo_codes').insert({
    code: input.code.toUpperCase().trim(),
    name: input.name ?? null,
    external_uuid: input.external_uuid ?? null,
    channel: input.channel ?? null,
    discount_pct: input.discount_pct ?? null,
    valid_from: input.valid_from || null,
    valid_until: input.valid_until || null,
    status: 'active',
  }).select('*').single()
  if (error) throw error
  return data as PromoCodeRow
}

export interface PromoUpdate {
  code?: string
  channel?: string | null
  discount_pct?: number | null
  valid_from?: string | null
  valid_until?: string | null
  status?: 'active' | 'paused' | 'expired' | 'archived'
  notes?: string | null
}

export async function updatePromoCode(id: number, patch: PromoUpdate): Promise<PromoCodeRow> {
  const payload: Record<string, unknown> = {}
  if (patch.code         != null) payload.code         = patch.code.toUpperCase().trim()
  if (patch.channel      !== undefined) payload.channel      = patch.channel ?? null
  if (patch.discount_pct !== undefined) payload.discount_pct = patch.discount_pct ?? null
  if (patch.valid_from   !== undefined) payload.valid_from   = patch.valid_from || null
  if (patch.valid_until  !== undefined) payload.valid_until  = patch.valid_until || null
  if (patch.status       != null) payload.status       = patch.status
  if (patch.notes        !== undefined) payload.notes        = patch.notes ?? null
  payload.updated_at = new Date().toISOString()

  const { data, error } = await supabase.schema('crm').from('promo_codes')
    .update(payload).eq('id', id).select('*').single()
  if (error) throw error
  return data as PromoCodeRow
}

export async function fetchPromoCodes(): Promise<PromoCodeRow[]> {
  const { data, error } = await supabase.schema('marketing').from('promo_codes').select('*').order('updated_at', { ascending: false })
  if (error) throw error
  return ((data ?? []) as PromoCodeRow[]).map((p) => ({
    ...p,
    discount_pct: p.discount_pct == null ? null : numToNumber(p.discount_pct),
  }))
}

export async function fetchPromoStatsWeekly(): Promise<PromoStatWeekly[]> {
  const { data, error } = await supabase.schema('marketing').from('promo_stats_weekly').select('*').order('week_start', { ascending: true })
  if (error) throw error
  return ((data ?? []) as Record<string, unknown>[]).map((r) => ({
    promo_code_id: r.promo_code_id as number,
    week_start: r.week_start as string,
    sales_rub: numToNumber(r.sales_rub as never),
    payout_rub: numToNumber(r.payout_rub as never),
    orders_count: numToNumber(r.orders_count as never),
    returns_count: numToNumber(r.returns_count as never),
    avg_discount_pct: numToNumber(r.avg_discount_pct as never),
    avg_check: numToNumber(r.avg_check as never),
  }))
}

export async function fetchPromoProductBreakdown(promoCodeId: number): Promise<PromoProductBreakdownRow[]> {
  const { data, error } = await supabase
    .schema('marketing').from('promo_product_breakdown')
    .select('*').eq('promo_code_id', promoCodeId)
    .order('amount_rub', { ascending: false })
  if (error) throw error
  return ((data ?? []) as Record<string, unknown>[]).map((r) => ({
    id:            r.id as number,
    promo_code_id: r.promo_code_id as number,
    week_start:    r.week_start    as string,
    artikul_id:    (r.artikul_id ?? null) as number | null,
    sku_label:     (r.sku_label    as string) ?? '—',
    model_code:    (r.model_code ?? null) as string | null,
    qty:           numToNumber(r.qty as never),
    amount_rub:    numToNumber(r.amount_rub as never),
  }))
}

export async function fetchPromoStatsForCode(promoCodeId: number): Promise<PromoStatWeekly[]> {
  const { data, error } = await supabase.schema('marketing').from('promo_stats_weekly')
    .select('*').eq('promo_code_id', promoCodeId).order('week_start', { ascending: true })
  if (error) throw error
  return ((data ?? []) as Record<string, unknown>[]).map((r) => ({
    promo_code_id: r.promo_code_id as number,
    week_start: r.week_start as string,
    sales_rub: numToNumber(r.sales_rub as never),
    payout_rub: numToNumber(r.payout_rub as never),
    orders_count: numToNumber(r.orders_count as never),
    returns_count: numToNumber(r.returns_count as never),
    avg_discount_pct: numToNumber(r.avg_discount_pct as never),
    avg_check: numToNumber(r.avg_check as never),
  }))
}
