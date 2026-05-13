/**
 * W9.18 — Человекочитаемые toast-ошибки вместо raw SQL/permission текстов.
 *
 * Переводит сырые ошибки Supabase / PostgREST / сети в понятный русский текст,
 * который можно показать пользователю в `alert()` / toast / inline-баннере.
 *
 * Оригинальная ошибка всегда логируется в console.error для отладки.
 *
 * Примеры маппинга:
 *  - code 42501 (permission denied)        → "Недостаточно прав…"
 *  - code 23505 (unique_violation)         → "Запись с таким значением уже существует."
 *  - code 23503 (foreign_key_violation)    → "Связанные данные не позволяют…"
 *  - code PGRST116 (no rows)               → "Запись не найдена."
 *  - сетевые сбои (TypeError: fetch failed)→ "Не удалось связаться с сервером…"
 *  - default                               → "Что-то пошло не так…"
 */

type MaybeError = {
  code?: string | number
  message?: string
  details?: string
  hint?: string
  name?: string
} | null | undefined

const GENERIC_FALLBACK =
  "Что-то пошло не так. Попробуйте ещё раз или сообщите разработчикам."
const PERMISSION_MSG =
  "Недостаточно прав на это действие. Обратитесь к администратору."
const NETWORK_MSG =
  "Не удалось связаться с сервером. Проверьте подключение."
const UNIQUE_MSG = "Запись с таким значением уже существует."
const FK_MSG = "Связанные данные не позволяют выполнить операцию."
const NOT_FOUND_MSG = "Запись не найдена."

/**
 * Извлечь объект ошибки-подобной структуры из произвольного значения.
 * Supabase возвращает { data, error: { code, message, details, hint } },
 * fetch выкидывает TypeError, обычный код — Error.
 */
function asMaybeError(input: unknown): MaybeError {
  if (input == null) return null
  if (typeof input === "object") return input as MaybeError
  if (typeof input === "string") return { message: input }
  return null
}

/**
 * Главный экспорт: получить русское сообщение об ошибке для показа в UI.
 * Всегда логирует оригинал в console.error('[catalog]', error).
 */
export function translateError(error: unknown): string {
  // eslint-disable-next-line no-console
  console.error("[catalog]", error)

  const err = asMaybeError(error)
  if (!err) return GENERIC_FALLBACK

  const code = err.code != null ? String(err.code) : ""
  const message = (err.message ?? "").toString()
  const details = (err.details ?? "").toString()
  const combined = `${message} ${details}`.toLowerCase()

  // PostgreSQL / Supabase коды (числовые SQLSTATE)
  switch (code) {
    case "42501":
      return PERMISSION_MSG
    case "23505":
      return UNIQUE_MSG
    case "23503":
      return FK_MSG
    case "PGRST116":
      return NOT_FOUND_MSG
    case "PGRST301":
      // JWT expired / authentication
      return "Сессия истекла. Войдите заново."
    default:
      break
  }

  // Текстовая эвристика: иногда code не приходит, только message
  if (combined.includes("permission denied")) return PERMISSION_MSG
  if (
    combined.includes("row-level security") ||
    combined.includes("violates row-level security")
  ) {
    return PERMISSION_MSG
  }
  if (combined.includes("duplicate key") || combined.includes("unique constraint")) {
    return UNIQUE_MSG
  }
  if (combined.includes("foreign key") || combined.includes("violates foreign key")) {
    return FK_MSG
  }

  // Сетевые сбои
  if (err.name === "TypeError" && combined.includes("fetch")) return NETWORK_MSG
  if (combined.includes("failed to fetch") || combined.includes("network")) {
    return NETWORK_MSG
  }
  if (combined.includes("networkerror") || combined.includes("abortederror")) {
    return NETWORK_MSG
  }

  return GENERIC_FALLBACK
}
