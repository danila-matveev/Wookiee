import { supabase } from '@/lib/supabase'
import type { PromoCodeRow, PromoStatWeekly } from '@/types/marketing'
import { numToNumber } from '@/lib/marketing-helpers'

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
