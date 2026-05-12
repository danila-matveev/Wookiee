import { supabase } from '@/lib/supabase'
import type { PromoCodeRow, PromoStatWeekly } from '@/types/marketing'
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

export interface UpdatePromoCodeInput {
  id: number
  code?: string
  channel?: string | null
  discount_pct?: number | null
  valid_from?: string | null
  valid_until?: string | null
}

export async function updatePromoCode(input: UpdatePromoCodeInput): Promise<void> {
  const { id, ...rest } = input
  const patch: Record<string, unknown> = { updated_at: new Date().toISOString() }
  if (rest.code !== undefined)         patch.code = rest.code
  if (rest.channel !== undefined)      patch.channel = rest.channel
  if (rest.discount_pct !== undefined) patch.discount_pct = rest.discount_pct
  if (rest.valid_from !== undefined)   patch.valid_from = rest.valid_from
  if (rest.valid_until !== undefined)  patch.valid_until = rest.valid_until

  const { error } = await supabase.schema('crm').from('promo_codes').update(patch).eq('id', id)
  if (error) throw new Error(error.message)
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
