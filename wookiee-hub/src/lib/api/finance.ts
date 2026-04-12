import { get } from "@/lib/api-client"
import type { ApiQueryParams, FinanceSummary, ModelRow } from "@/types/api"

export function fetchFinanceSummary(params: ApiQueryParams) {
  return get<FinanceSummary>("/api/finance/summary", params)
}

export async function fetchFinanceByModel(params: ApiQueryParams) {
  const res = await get<{ rows: ModelRow[] }>("/api/finance/by-model", params)
  return res.rows
}
