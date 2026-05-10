export type SearchQuerySource = 'branded_queries' | 'substitute_articles'

export function parseUnifiedId(unifiedId: string): { source: SearchQuerySource; id: number } {
  if (unifiedId.length < 2) throw new Error(`Invalid unified_id: ${unifiedId}`)
  const prefix = unifiedId[0]
  const id = Number(unifiedId.slice(1))
  if (Number.isNaN(id)) throw new Error(`Invalid unified_id: ${unifiedId}`)
  if (prefix === 'B') return { source: 'branded_queries', id }
  if (prefix === 'S') return { source: 'substitute_articles', id }
  throw new Error(`Unknown unified_id prefix: ${prefix}`)
}

/** Supabase JS returns Postgres numeric as string. Coerce safely. */
export const numToNumber = (v: number | string | null | undefined): number => {
  if (v == null) return 0
  if (typeof v === 'number') return v
  const n = Number(v)
  return Number.isFinite(n) ? n : 0
}
