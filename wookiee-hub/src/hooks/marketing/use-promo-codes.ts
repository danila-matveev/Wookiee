import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createPromoCode,
  fetchPromoCodes,
  fetchPromoStatsWeekly,
  updatePromoCode,
  type PromoCreate,
  type UpdatePromoCodeInput,
} from '@/api/marketing/promo-codes'
import type { PromoCodeRow } from '@/types/marketing'

export const promoCodesKeys = {
  all:    ['marketing', 'promo-codes'] as const,
  list:   () => [...promoCodesKeys.all, 'list'] as const,
  stats:  () => [...promoCodesKeys.all, 'stats'] as const,
}

export function usePromoCodes()       { return useQuery({ queryKey: promoCodesKeys.list(),  queryFn: fetchPromoCodes,       staleTime: 5 * 60_000 }) }
export function usePromoStatsWeekly() { return useQuery({ queryKey: promoCodesKeys.stats(), queryFn: fetchPromoStatsWeekly, staleTime: 60_000 }) }

export function useCreatePromoCode() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createPromoCode,
    onMutate: async (input: PromoCreate) => {
      await qc.cancelQueries({ queryKey: promoCodesKeys.list() })
      const prev = qc.getQueryData<PromoCodeRow[]>(promoCodesKeys.list()) ?? []
      const optimistic: PromoCodeRow = {
        id: -Date.now(),
        code: input.code.toUpperCase().trim(),
        name: input.name ?? null,
        external_uuid: input.external_uuid ?? null,
        channel: input.channel ?? null,
        discount_pct: input.discount_pct ?? null,
        valid_from: input.valid_from ?? null,
        valid_until: input.valid_until ?? null,
        status: 'active',
        notes: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      }
      qc.setQueryData<PromoCodeRow[]>(promoCodesKeys.list(), [optimistic, ...prev])
      return { prev }
    },
    onError: (_err: unknown, _input: PromoCreate, ctx?: { prev: PromoCodeRow[] }) => {
      if (ctx?.prev) qc.setQueryData(promoCodesKeys.list(), ctx.prev)
    },
    onSettled: () => qc.invalidateQueries({ queryKey: promoCodesKeys.list() }),
  })
}

export function useUpdatePromoCode() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: UpdatePromoCodeInput) => updatePromoCode(input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: promoCodesKeys.list() })
    },
  })
}
