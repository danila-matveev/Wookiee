import { supabase } from '@/lib/supabase'

const ANALYTICS_API_URL = import.meta.env.VITE_ANALYTICS_API_URL ?? ''
const ANALYTICS_API_KEY = import.meta.env.VITE_ANALYTICS_API_KEY ?? ''

/**
 * Catalog mirror sync. Each option maps to a sheet tab name in the mirror
 * spreadsheet (see services/sheets_sync/hub_to_sheets/config.SHEET_SPECS).
 * "all" — sync every sheet.
 */
export const CATALOG_SYNC_OPTIONS = [
  { value: 'all',              label: 'Всё'             },
  { value: 'Все модели',       label: 'Модели'          },
  { value: 'Все артикулы',     label: 'Артикулы'        },
  { value: 'Все товары',       label: 'Товары'          },
  { value: 'Аналитики цветов', label: 'Цвета'           },
  { value: 'Склейки WB',       label: 'Склейки WB'      },
  { value: 'Склейки Озон',     label: 'Склейки Озон'    },
] as const

export type CatalogSyncSheet = (typeof CATALOG_SYNC_OPTIONS)[number]['value']

export const CATALOG_TOOL_SLUG = 'catalog-sheets-mirror'

export interface SyncMirrorResponse {
  status: 'ok' | 'error'
  sheet: string
  duration_ms: number
  cells_updated: number
  rows_appended: number
  rows_deleted: number
  sheets_synced: string[]
  errors: Array<{ sheet?: string; error: string }>
  run_id: string | null
}

export interface SyncMirrorStatus {
  run_id?: string
  status: 'never_run' | 'running' | 'success' | 'error'
  started_at?: string | null
  finished_at?: string | null
  duration_ms?: number | null
  output_summary?: string | null
  error_message?: string | null
  triggered_by?: string | null
}

function syncUrl(path: string): string {
  const base = ANALYTICS_API_URL || window.location.origin
  return new URL(path, base).toString()
}

async function authHeaders(): Promise<HeadersInit> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  if (token) headers['Authorization'] = `Bearer ${token}`
  if (ANALYTICS_API_KEY) headers['X-API-Key'] = ANALYTICS_API_KEY
  return headers
}

export async function triggerCatalogSync(sheet: CatalogSyncSheet): Promise<SyncMirrorResponse> {
  const r = await fetch(syncUrl('/api/catalog/sync-mirror'), {
    method: 'POST',
    headers: await authHeaders(),
    body: JSON.stringify({ sheet }),
  })
  if (!r.ok) {
    const text = await r.text().catch(() => r.statusText)
    throw new Error(`Sync failed (${r.status}): ${text}`)
  }
  return r.json()
}

export async function fetchCatalogSyncStatus(): Promise<SyncMirrorStatus> {
  const r = await fetch(syncUrl('/api/catalog/sync-mirror/status'), {
    headers: await authHeaders(),
  })
  if (!r.ok) {
    const text = await r.text().catch(() => r.statusText)
    throw new Error(`Status failed (${r.status}): ${text}`)
  }
  return r.json()
}
