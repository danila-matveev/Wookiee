// Helpers for model-level completeness and shape utilities.
//
// `computeModelCompleteness` is the canonical 0..1 completeness scoring used
// by the Matrix table («Заполненность» column) and ModelCard sidebar.
//
// We score 10 key fields uniformly; any value that is null/undefined/"" counts
// as missing. Fields are picked to cover the basic dimensions a buyer/seller
// fills out for every model: classification (kategoriya/kollekciya/fabrika),
// lifecycle (status), content (nazvanie_etiketka/opisanie_sayt/material),
// production basics (ves_kg, kratnost_koroba, razmery_modeli).

import type { ModelOsnova } from "@/types/catalog"

const COMPLETENESS_FIELDS: readonly (keyof ModelOsnova)[] = [
  "kategoriya_id",
  "kollekciya_id",
  "fabrika_id",
  "status_id",
  "nazvanie_etiketka",
  "opisanie_sayt",
  "material",
  "ves_kg",
  "kratnost_koroba",
  "razmery_modeli",
]

function isFilled(value: unknown): boolean {
  if (value === null || value === undefined) return false
  if (typeof value === "string" && value.trim() === "") return false
  return true
}

/**
 * Доля заполненности ключевых полей `modeli_osnova`. Возвращает число 0..1.
 * Используется в матрице (CompletenessRing 16px) и в сайдбаре ModelCard
 * (CompletenessRing 56px).
 */
export function computeModelCompleteness(model: Partial<ModelOsnova>): number {
  let filled = 0
  for (const key of COMPLETENESS_FIELDS) {
    if (isFilled(model[key as keyof ModelOsnova])) filled += 1
  }
  return filled / COMPLETENESS_FIELDS.length
}

/** Сколько полей сейчас заполнено / всего — для подписи под кольцом. */
export function modelCompletenessCounts(model: Partial<ModelOsnova>): {
  filled: number
  total: number
} {
  let filled = 0
  for (const key of COMPLETENESS_FIELDS) {
    if (isFilled(model[key as keyof ModelOsnova])) filled += 1
  }
  return { filled, total: COMPLETENESS_FIELDS.length }
}

/** Базовые поля, по которым считается completeness — экспортируем для тестов. */
export const MODEL_COMPLETENESS_FIELDS = COMPLETENESS_FIELDS

// ─── W9.8: канонический размерный ряд модели ──────────────────────────────
// Источник истины — `modeli_osnova.razmery_modeli` (CSV/JSON-строка), которую
// пользователь редактирует в карточке модели. До W9.8 матрица собирала размеры
// из `modeli.rossiyskiy_razmer` (это российский numeric-код вариации, не lad-
// der), из-за чего отображение было либо пустым, либо неверным (например, для
// Ruby показывалось 4 значения, реальный комплект — 3: S/M/L). Теперь матрица
// читает CSV razmery_modeli — тот же источник, что и карточка модели.

/** Распарсить CSV/JSON значение razmery_modeli → массив размеров (XS..XXL). */
export function parseRazmeryModeli(raw: string | null | undefined): string[] {
  if (!raw) return []
  const trimmed = String(raw).trim()
  if (!trimmed) return []
  // accept JSON array
  if (trimmed.startsWith("[")) {
    try {
      const parsed = JSON.parse(trimmed)
      if (Array.isArray(parsed)) {
        return parsed
          .map((s) => String(s).trim())
          .filter(Boolean)
      }
    } catch {
      // fall through to CSV
    }
  }
  return trimmed
    .split(/[,;\s]+/)
    .map((s) => s.trim())
    .filter(Boolean)
}
