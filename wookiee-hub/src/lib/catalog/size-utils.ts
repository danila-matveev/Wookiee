// Физическая сортировка размеров одежды (W10.4 / W10.29).
//
// Проблема: при alpha-сорте размеров "M" уходит выше "S", потому что 'L' < 'M' < 'S'
// по латинице. Юзер видит, что строки SKU "прыгают" при смене статуса — это
// из-за того, что сортировка нестабильная и/или alphabetic.
//
// Решение: физический ladder XXS..5XL (как на размерной шкале). Числовые
// размеры (40, 42, …) идут после буквенных через offset 100. Неизвестные —
// в конец (999).
//
// ВАЖНО: эта функция предназначена ТОЛЬКО для сортировки. Не использовать как
// валидатор «такой ли это размер» — для этого есть `RAZMER_LADDER` ниже.

/** Канонический порядок буквенных размеров (S, M, L, …). */
export const RAZMER_LADDER = [
  "XXS",
  "XS",
  "S",
  "M",
  "L",
  "XL",
  "XXL",
  "3XL",
  "4XL",
  "5XL",
] as const

export type RazmerLetter = typeof RAZMER_LADDER[number]

/**
 * Порядковый номер размера для сортировки.
 *
 * Алгоритм:
 *   1. null / undefined / "" → 999 (в конец)
 *   2. буквенный (XS, S, M, …) → индекс в `RAZMER_LADDER` (0..9)
 *   3. числовой (40, 42, …) → 100 + число (так буквенные всегда впереди)
 *   4. что-то невнятное → 999
 */
export function razmerOrder(razmer: string | null | undefined): number {
  if (!razmer) return 999
  const trimmed = razmer.trim()
  if (trimmed === "") return 999
  const upper = trimmed.toUpperCase()
  const idx = (RAZMER_LADDER as readonly string[]).indexOf(upper)
  if (idx >= 0) return idx
  // Числовой размер — допускаем суффикс ("44/46", "44T") и берём первое число.
  const num = parseInt(trimmed, 10)
  if (!Number.isNaN(num)) return 100 + num
  return 999
}

/**
 * Стабильный компаратор размеров для `Array.prototype.sort`.
 * Возвращает <0, 0, >0 по `razmerOrder(a) - razmerOrder(b)`.
 *
 * Использование:
 *   rows.sort((a, b) => compareRazmer(a.razmer, b.razmer))
 *
 * Для composite ordering (сначала по цвету, потом по размеру):
 *   rows.sort((a, b) => {
 *     const c = (a.cvet ?? "").localeCompare(b.cvet ?? "")
 *     return c !== 0 ? c : compareRazmer(a.razmer, b.razmer)
 *   })
 */
export function compareRazmer(
  a: string | null | undefined,
  b: string | null | undefined,
): number {
  return razmerOrder(a) - razmerOrder(b)
}
