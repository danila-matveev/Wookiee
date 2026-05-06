import { supabase } from "@/lib/supabase"
import type { RnpResponse, RnpModelsResponse } from "@/types/rnp"

const BASE = import.meta.env.VITE_ANALYTICS_API_URL ?? "https://analytics-api.os.wookiee.shop"

async function authHeaders(): Promise<Record<string, string>> {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  if (!token) throw new Error("No active session — please log in again")
  return { Authorization: `Bearer ${token}` }
}

export async function fetchRnpModels(): Promise<RnpModelsResponse> {
  const res = await fetch(`${BASE}/api/rnp/models?marketplace=wb`, {
    headers: await authHeaders(),
  })
  if (!res.ok) throw new Error(`fetchRnpModels: ${res.status}`)
  return res.json()
}

export async function fetchRnpWeeks(params: {
  model: string
  dateFrom: string  // YYYY-MM-DD
  dateTo: string
  buyoutForecast?: number
}): Promise<RnpResponse> {
  const url = new URL(`${BASE}/api/rnp/weeks`)
  url.searchParams.set("model", params.model)
  url.searchParams.set("date_from", params.dateFrom)
  url.searchParams.set("date_to", params.dateTo)
  if (params.buyoutForecast !== undefined) {
    url.searchParams.set("buyout_forecast", String(params.buyoutForecast))
  }
  const res = await fetch(url.toString(), { headers: await authHeaders() })
  if (!res.ok) throw new Error(`fetchRnpWeeks: ${res.status}`)
  return res.json()
}
