import { useQuery } from '@tanstack/react-query'
import { fetchPromoCodes, fetchPromoStatsWeekly } from '@/api/marketing/promo-codes'

export const promoCodesKeys = {
  all:    ['marketing', 'promo-codes'] as const,
  list:   () => [...promoCodesKeys.all, 'list'] as const,
  stats:  () => [...promoCodesKeys.all, 'stats'] as const,
}

export function usePromoCodes()       { return useQuery({ queryKey: promoCodesKeys.list(),  queryFn: fetchPromoCodes,       staleTime: 5 * 60_000 }) }
export function usePromoStatsWeekly() { return useQuery({ queryKey: promoCodesKeys.stats(), queryFn: fetchPromoStatsWeekly, staleTime: 60_000 }) }
