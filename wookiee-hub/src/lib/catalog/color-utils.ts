// Deterministic swatch color from color_code (fallback when hex is missing)
export function swatchColor(colorCode: string): string {
  let hash = 0
  for (let i = 0; i < colorCode.length; i++) {
    hash = (colorCode.charCodeAt(i) + ((hash << 5) - hash)) | 0
  }
  const h = Math.abs(hash) % 360
  return `hsl(${h}, 42%, 62%)`
}

// Resolve display swatch — prefer real hex from DB, fall back to deterministic hue.
export function resolveSwatch(hex: string | null | undefined, colorCode: string): string {
  if (hex && /^#[0-9A-Fa-f]{6}$/.test(hex)) return hex
  return swatchColor(colorCode)
}

// ── HEX helpers ───────────────────────────────────────────────────────────

export function isValidHex(hex: string | null | undefined): hex is string {
  return !!hex && /^#[0-9A-Fa-f]{6}$/.test(hex)
}

export function hexToRgb(hex: string): { r: number; g: number; b: number } | null {
  if (!isValidHex(hex)) return null
  return {
    r: parseInt(hex.slice(1, 3), 16),
    g: parseInt(hex.slice(3, 5), 16),
    b: parseInt(hex.slice(5, 7), 16),
  }
}

/** Euclidean distance in RGB space. Both args must be valid hex (#RRGGBB). */
export function colorDistance(hex1: string, hex2: string): number {
  const a = hexToRgb(hex1)
  const b = hexToRgb(hex2)
  if (!a || !b) return Number.POSITIVE_INFINITY
  const dr = a.r - b.r
  const dg = a.g - b.g
  const db = a.b - b.b
  return Math.sqrt(dr * dr + dg * dg + db * db)
}

/** Find N most-similar colors (by RGB distance). Skips entries without valid hex. */
export function findSimilarColors<T extends { hex: string | null }>(
  target: { hex: string | null },
  pool: T[],
  limit = 6,
): T[] {
  if (!isValidHex(target.hex)) return []
  return pool
    .filter((c) => isValidHex(c.hex))
    .map((c) => ({ c, d: colorDistance(target.hex as string, c.hex as string) }))
    .sort((a, b) => a.d - b.d)
    .slice(0, limit)
    .map((x) => x.c)
}

// Relative date string
export function relativeDate(iso: string | null | undefined): string {
  if (!iso) return "—"
  const d = new Date(iso)
  const now = new Date()
  const diff = Math.floor((now.getTime() - d.getTime()) / 86400000)
  if (diff === 0) return "сегодня"
  if (diff === 1) return "вчера"
  if (diff < 7) return `${diff} д. назад`
  if (diff < 30) return `${Math.floor(diff / 7)} нед. назад`
  if (diff < 365) return `${Math.floor(diff / 30)} мес. назад`
  return `${Math.floor(diff / 365)} г. назад`
}

// Category-specific attribute keys (Опция Б: inline config)
export const ATTRIBUTES_BY_CATEGORY: Record<number, string[]> = {
  1: ["stepen_podderzhki", "forma_chashki", "regulirovka", "zastezhka", "dlya_kakoy_grudi", "posadka_trusov", "vid_trusov", "naznachenie", "stil", "po_nastroeniyu"],
  2: ["posadka_trusov", "vid_trusov", "naznachenie", "stil", "po_nastroeniyu"],
  3: ["stepen_podderzhki", "zastezhka", "naznachenie", "stil", "po_nastroeniyu"],
  4: ["stepen_podderzhki", "forma_chashki", "regulirovka", "zastezhka", "dlya_kakoy_grudi", "naznachenie", "stil", "po_nastroeniyu"],
  5: ["stepen_podderzhki", "naznachenie", "stil", "po_nastroeniyu"],
}

export const ATTRIBUTE_LABELS: Record<string, string> = {
  stepen_podderzhki: "Степень поддержки",
  forma_chashki: "Форма чашки",
  regulirovka: "Регулировка",
  zastezhka: "Застёжка",
  dlya_kakoy_grudi: "Для какой груди",
  posadka_trusov: "Посадка",
  vid_trusov: "Вид трусов",
  naznachenie: "Назначение",
  stil: "Стиль",
  po_nastroeniyu: "По настроению",
}

export const TIPY_KOLLEKCII = [
  "Трикотажное белье",
  "Бесшовное белье Jelly",
  "Бесшовное белье Audrey",
]

// Canonical list of 18 ключевых полей `modeli_osnova`, по которым считается
// заполненность в матрице.  Порядок отражает приоритет (primary → secondary
// → tertiary → physical) и используется для сортировки tooltip-а
// «незаполненные поля» — самые важные сверху.
export interface CompletenessField {
  key: string
  label: string
  /** Pretty share (pp) этого поля в общем completeness. Сумма ≈ 100. */
  weight: number
}

const COMPLETENESS_KEY_FIELDS: readonly string[] = [
  // primary — классификация и идентификация
  "kod", "kategoriya_id", "kollekciya_id", "fabrika_id", "tip_kollekcii",
  // secondary — контент и описания
  "nazvanie_etiketka", "nazvanie_sayt", "opisanie_sayt",
  // tertiary — производство и логистика
  "sostav_syrya", "razmery_modeli", "sku_china", "tnved", "gruppa_sertifikata",
  // physical — габариты
  "ves_kg", "dlina_cm", "shirina_cm", "vysota_cm", "kratnost_koroba",
] as const

const COMPLETENESS_FIELD_LABELS: Record<string, string> = {
  kod: "Код",
  kategoriya_id: "Категория",
  kollekciya_id: "Коллекция",
  fabrika_id: "Фабрика",
  tip_kollekcii: "Тип коллекции",
  nazvanie_etiketka: "Название (этикетка)",
  nazvanie_sayt: "Название (сайт)",
  opisanie_sayt: "Описание (сайт)",
  sostav_syrya: "Состав сырья",
  razmery_modeli: "Размеры модели",
  sku_china: "SKU фабрики",
  tnved: "ТН ВЭД",
  gruppa_sertifikata: "Группа сертификата",
  ves_kg: "Вес, кг",
  dlina_cm: "Длина, см",
  shirina_cm: "Ширина, см",
  vysota_cm: "Высота, см",
  kratnost_koroba: "Кратность короба",
}

function isFilledValue(v: unknown): boolean {
  return v !== null && v !== undefined && v !== ""
}

// Compute completeness ratio client-side
export function computeCompleteness(m: Record<string, unknown>): number {
  const filled = COMPLETENESS_KEY_FIELDS.filter((k) => isFilledValue(m[k])).length
  return filled / COMPLETENESS_KEY_FIELDS.length
}

/**
 * Список незаполненных ключевых полей с весами (pp). Используется в tooltip
 * над CompletenessRing — пользователь сразу видит, чего не хватает.
 */
export function getMissingFields(m: Record<string, unknown>): CompletenessField[] {
  const weightPerField = 100 / COMPLETENESS_KEY_FIELDS.length
  return COMPLETENESS_KEY_FIELDS
    .filter((k) => !isFilledValue(m[k]))
    .map((k) => ({
      key: k,
      label: COMPLETENESS_FIELD_LABELS[k] ?? k,
      weight: Math.round(weightPerField * 10) / 10,
    }))
}

export const SEMEYSTVA = [
  { kod: "tricot", nazvanie: "Трикотаж" },
  { kod: "jelly",  nazvanie: "Jelly" },
  { kod: "audrey", nazvanie: "Audrey" },
  { kod: "sets",   nazvanie: "Sets" },
  { kod: "other",  nazvanie: "Другие" },
]
