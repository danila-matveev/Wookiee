/**
 * Static column definitions for modeli_osnova table.
 *
 * The backend FieldDefinitions are out of sync with the actual DB schema,
 * so we define columns here matching the real ModelOsnova model.
 */
import type { LookupItem } from "@/lib/matrix-api"
import type { Column } from "@/components/matrix/data-table"
import { LOOKUP_TABLE_MAP } from "@/components/matrix/panel/types"

type LookupCache = Record<string, LookupItem[]>

interface ModelColumnDef {
  key: string
  label: string
  type: "text" | "number" | "select" | "date"
  section: string
  defaultVisible: boolean
}

/**
 * All columns matching actual modeli_osnova DB columns.
 * `defaultVisible` controls which show by default in the table.
 */
const MODEL_COLUMN_DEFS: ModelColumnDef[] = [
  // Основные — visible by default
  { key: "kod", label: "Код модели", type: "text", section: "Основные", defaultVisible: true },
  { key: "kategoriya_id", label: "Категория", type: "select", section: "Основные", defaultVisible: true },
  { key: "kollekciya_id", label: "Коллекция", type: "select", section: "Основные", defaultVisible: true },
  { key: "fabrika_id", label: "Фабрика", type: "select", section: "Основные", defaultVisible: true },
  { key: "tip_kollekcii", label: "Тип коллекции", type: "text", section: "Основные", defaultVisible: true },
  { key: "razmery_modeli", label: "Размеры", type: "text", section: "Основные", defaultVisible: true },

  // Производство и упаковка
  { key: "sku_china", label: "SKU China", type: "text", section: "Производство", defaultVisible: false },
  { key: "upakovka", label: "Упаковка", type: "text", section: "Производство", defaultVisible: false },
  { key: "kratnost_koroba", label: "Кратность короба", type: "number", section: "Производство", defaultVisible: false },
  { key: "srok_proizvodstva", label: "Срок производства", type: "text", section: "Производство", defaultVisible: false },
  { key: "komplektaciya", label: "Комплектация", type: "text", section: "Производство", defaultVisible: false },

  // Габариты
  { key: "ves_kg", label: "Вес (кг)", type: "number", section: "Габариты", defaultVisible: false },
  { key: "dlina_cm", label: "Длина (см)", type: "number", section: "Габариты", defaultVisible: false },
  { key: "shirina_cm", label: "Ширина (см)", type: "number", section: "Габариты", defaultVisible: false },
  { key: "vysota_cm", label: "Высота (см)", type: "number", section: "Габариты", defaultVisible: false },

  // Материал
  { key: "material", label: "Материал", type: "text", section: "Материал", defaultVisible: false },
  { key: "sostav_syrya", label: "Состав сырья", type: "text", section: "Материал", defaultVisible: false },
  { key: "composition", label: "Composition (EN)", type: "text", section: "Материал", defaultVisible: false },

  // Логистика
  { key: "tnved", label: "ТНВЭД", type: "text", section: "Логистика", defaultVisible: false },
  { key: "gruppa_sertifikata", label: "Группа серт.", type: "text", section: "Логистика", defaultVisible: false },

  // Контент
  { key: "nazvanie_etiketka", label: "Этикетка", type: "text", section: "Контент", defaultVisible: false },
  { key: "nazvanie_sayt", label: "Название (сайт)", type: "text", section: "Контент", defaultVisible: false },
  { key: "opisanie_sayt", label: "Описание (сайт)", type: "text", section: "Контент", defaultVisible: false },
  { key: "tegi", label: "Теги", type: "text", section: "Контент", defaultVisible: false },

  // Системные
  { key: "created_at", label: "Создано", type: "date", section: "Системные", defaultVisible: false },
  { key: "updated_at", label: "Обновлено", type: "date", section: "Системные", defaultVisible: false },
]

// ── Helpers ──────────────────────────────────────────────────────────────────

function formatDate(raw: unknown): string {
  if (raw == null) return "\u2014"
  const str = String(raw)
  try {
    const d = new Date(str)
    if (isNaN(d.getTime())) return str
    return d.toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric" })
  } catch {
    return str
  }
}

// ── Public API ───────────────────────────────────────────────────────────────

/** Column definitions for the column visibility popover */
export const MODEL_FIELD_DEFS = MODEL_COLUMN_DEFS

/** Default hidden fields for models (not defaultVisible) */
export const MODEL_DEFAULT_HIDDEN = new Set(
  MODEL_COLUMN_DEFS.filter((d) => !d.defaultVisible).map((d) => d.key),
)

/** Build table columns from static definitions + lookup cache */
export function buildModelColumns<T>(
  lookupCache: LookupCache,
  hiddenFields: Set<string>,
): Column<T>[] {
  return MODEL_COLUMN_DEFS
    .filter((def) => !hiddenFields.has(def.key))
    .map((def) => {
      const lookupTable = LOOKUP_TABLE_MAP[def.key]

      // Reference fields — resolve via lookup cache
      if (lookupTable) {
        const items = lookupCache[lookupTable] ?? []
        return {
          key: def.key,
          label: def.label,
          render: (row: T) => {
            const id = (row as Record<string, unknown>)[def.key]
            if (id == null) return "\u2014"
            const found = items.find((item) => item.id === Number(id))
            return found?.nazvanie ?? "\u2014"
          },
        }
      }

      // Date fields
      if (def.type === "date") {
        return {
          key: def.key,
          label: def.label,
          render: (row: T) => formatDate((row as Record<string, unknown>)[def.key]),
        }
      }

      return { key: def.key, label: def.label }
    })
}
