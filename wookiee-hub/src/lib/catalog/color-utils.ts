// Deterministic swatch color from color_code (no hex in DB)
export function swatchColor(colorCode: string): string {
  let hash = 0
  for (let i = 0; i < colorCode.length; i++) {
    hash = (colorCode.charCodeAt(i) + ((hash << 5) - hash)) | 0
  }
  const h = Math.abs(hash) % 360
  return `hsl(${h}, 42%, 62%)`
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

// Compute completeness ratio client-side
export function computeCompleteness(m: Record<string, unknown>): number {
  const key_fields = [
    "kod", "kategoriya_id", "kollekciya_id", "fabrika_id", "tip_kollekcii",
    "sostav_syrya", "razmery_modeli", "sku_china", "ves_kg",
    "dlina_cm", "shirina_cm", "vysota_cm", "kratnost_koroba",
    "nazvanie_etiketka", "nazvanie_sayt", "opisanie_sayt", "tnved",
    "gruppa_sertifikata",
  ]
  const filled = key_fields.filter((k) => {
    const v = m[k]
    return v !== null && v !== undefined && v !== ""
  }).length
  return filled / key_fields.length
}

export const SEMEYSTVA = [
  { kod: "tricot", nazvanie: "Трикотаж" },
  { kod: "jelly",  nazvanie: "Jelly" },
  { kod: "audrey", nazvanie: "Audrey" },
  { kod: "sets",   nazvanie: "Sets" },
  { kod: "other",  nazvanie: "Другие" },
]
