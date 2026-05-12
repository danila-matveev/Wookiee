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

const RU_MONTHS_SHORT = ['янв','фев','мар','апр','мая','июн','июл','авг','сен','окт','ноя','дек']

/** "2026-04-20" -> "20 апр". Used in weekly tables to match marketing v4 spec. */
export function formatWeekShort(iso: string): string {
  if (!iso || iso.length < 10) return iso
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return `${String(d.getDate()).padStart(2, '0')} ${RU_MONTHS_SHORT[d.getMonth()]}`
}

/**
 * Promo display status — derived from DB status + presence of channel.
 * Matches the marketing v4 spec which uses an "unidentified" pseudo-state for promos
 * that arrived from raw WB feeds without a known channel mapping.
 */
export type PromoDisplayStatus =
  | { kind: 'active';       label: 'Активен';      tone: 'success'   }
  | { kind: 'no_data';      label: 'Нет данных';   tone: 'secondary' }
  | { kind: 'unidentified'; label: 'Не идентиф.';  tone: 'warning'   }
  | { kind: 'paused';       label: 'На паузе';     tone: 'info'      }
  | { kind: 'expired';      label: 'Истёк';        tone: 'warning'   }
  | { kind: 'archived';     label: 'Архив';        tone: 'secondary' }

export function derivePromoStatus(args: {
  status:  'active' | 'paused' | 'expired' | 'archived'
  qty:     number
  channel: string | null
}): PromoDisplayStatus {
  if (args.status === 'paused')   return { kind: 'paused',   label: 'На паузе', tone: 'info'      }
  if (args.status === 'expired')  return { kind: 'expired',  label: 'Истёк',    tone: 'warning'   }
  if (args.status === 'archived') return { kind: 'archived', label: 'Архив',    tone: 'secondary' }
  // status === 'active' below
  if (args.qty > 0 && args.channel == null) return { kind: 'unidentified', label: 'Не идентиф.', tone: 'warning'   }
  if (args.qty === 0)                       return { kind: 'no_data',      label: 'Нет данных',  tone: 'secondary' }
  return { kind: 'active', label: 'Активен', tone: 'success' }
}
