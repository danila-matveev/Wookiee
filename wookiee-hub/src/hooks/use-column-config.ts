import { useCallback, useEffect, useMemo, useRef, useState } from "react"

/**
 * W9.5 — единый стейт-менеджер видимости и порядка колонок для всех трёх
 * реестров каталога: матрица, артикулы, SKU/товары.
 *
 * Контракт:
 * - `defaults` — полный набор колонок (включая поля, которые скрыты по умолчанию).
 * - возвращает `order` (массив ключей в текущем порядке отображения) и
 *   `visibility` (map ключ → bool). `visibleColumns` — упорядоченный список
 *   только видимых ключей.
 * - персистится в localStorage по ключу `catalog-<pageKey>-columns-v2`.
 * - при появлении новых дефолтных колонок в коде (которых ещё не было в
 *   сохранённом профиле) они автоматически дозаписываются в `order`
 *   с дефолтной видимостью; убранные из кода — выкидываются.
 */

export type CatalogPageKey = "matrix" | "artikuly" | "tovary"

export interface ColumnDescriptor {
  key: string
  label: string
  /** Видимость по умолчанию (первый запуск / Reset). */
  default: boolean
  /** Опциональный бейдж рядом с лейблом в UI конфигуратора. */
  badge?: string
  /** Группа для UX-секций в дропдауне ("Основные", "Каналы", "Маркетплейсы", …). */
  group?: string
  /** Подсказка-описание для tooltip в конфигураторе. */
  description?: string
}

interface StoredProfile {
  order: string[]
  visibility: Record<string, boolean>
  version: 2
}

interface ColumnConfigState {
  /** Полный упорядоченный список ключей (видимые и скрытые). */
  order: string[]
  /** Видимость по ключу. */
  visibility: Record<string, boolean>
  /** Видимые ключи в порядке, готовый массив для `columns.map(...)` в таблице. */
  visibleColumns: string[]
  setVisibility: (key: string, visible: boolean) => void
  toggleVisibility: (key: string) => void
  setOrder: (newOrder: string[]) => void
  moveColumn: (fromKey: string, toKey: string) => void
  /** Сброс к дефолтному профилю (порядок и видимость из `defaults`). */
  reset: () => void
  /** Все доступные колонки (исходный список, без сортировки/фильтрации). */
  all: ColumnDescriptor[]
}

function storageKey(pageKey: CatalogPageKey): string {
  return `catalog-${pageKey}-columns-v2`
}

function buildDefaultProfile(defaults: ColumnDescriptor[]): StoredProfile {
  return {
    version: 2,
    order: defaults.map((c) => c.key),
    visibility: Object.fromEntries(defaults.map((c) => [c.key, c.default])),
  }
}

function mergeWithDefaults(
  stored: StoredProfile | null,
  defaults: ColumnDescriptor[],
): StoredProfile {
  const base = buildDefaultProfile(defaults)
  if (!stored || stored.version !== 2) return base

  const defaultKeys = new Set(base.order)
  // Filter stored order: только живые ключи, в их сохранённом порядке.
  const filteredOrder = stored.order.filter((k) => defaultKeys.has(k))
  // Дозаписать новые ключи (добавленные в код после первого сохранения).
  for (const k of base.order) {
    if (!filteredOrder.includes(k)) filteredOrder.push(k)
  }

  const visibility: Record<string, boolean> = {}
  for (const k of filteredOrder) {
    visibility[k] = stored.visibility[k] ?? (base.visibility[k] ?? false)
  }

  return { version: 2, order: filteredOrder, visibility }
}

function readProfile(pageKey: CatalogPageKey, defaults: ColumnDescriptor[]): StoredProfile {
  if (typeof window === "undefined") return buildDefaultProfile(defaults)
  try {
    const raw = window.localStorage.getItem(storageKey(pageKey))
    if (!raw) return buildDefaultProfile(defaults)
    const parsed = JSON.parse(raw) as StoredProfile | null
    return mergeWithDefaults(parsed, defaults)
  } catch {
    return buildDefaultProfile(defaults)
  }
}

function writeProfile(pageKey: CatalogPageKey, profile: StoredProfile): void {
  if (typeof window === "undefined") return
  try {
    window.localStorage.setItem(storageKey(pageKey), JSON.stringify(profile))
  } catch {
    // best-effort
  }
}

export function useColumnConfig(
  pageKey: CatalogPageKey,
  defaults: ColumnDescriptor[],
): ColumnConfigState {
  const defaultsRef = useRef(defaults)
  // Update defaults ref if the array identity changes; useful for HMR / dynamic.
  defaultsRef.current = defaults

  const [profile, setProfile] = useState<StoredProfile>(() =>
    readProfile(pageKey, defaults),
  )

  // Если набор дефолтов изменился (например, после обновления приложения с
  // новыми колонками) — пересобрать профиль из localStorage + новый defaults.
  useEffect(() => {
    setProfile((prev) => mergeWithDefaults(prev, defaultsRef.current))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [defaults.map((c) => c.key).join("|")])

  // Persist on every change.
  useEffect(() => {
    writeProfile(pageKey, profile)
  }, [pageKey, profile])

  const setVisibility = useCallback((key: string, visible: boolean) => {
    setProfile((p) => ({
      ...p,
      visibility: { ...p.visibility, [key]: visible },
    }))
  }, [])

  const toggleVisibility = useCallback((key: string) => {
    setProfile((p) => ({
      ...p,
      visibility: { ...p.visibility, [key]: !p.visibility[key] },
    }))
  }, [])

  const setOrder = useCallback((newOrder: string[]) => {
    setProfile((p) => {
      const allowed = new Set(defaultsRef.current.map((c) => c.key))
      const filtered = newOrder.filter((k) => allowed.has(k))
      // Дописать недостающие ключи в конец (на случай, если drag-список — урезанный).
      for (const k of defaultsRef.current.map((c) => c.key)) {
        if (!filtered.includes(k)) filtered.push(k)
      }
      return { ...p, order: filtered }
    })
  }, [])

  const moveColumn = useCallback((fromKey: string, toKey: string) => {
    setProfile((p) => {
      if (fromKey === toKey) return p
      const idxFrom = p.order.indexOf(fromKey)
      const idxTo = p.order.indexOf(toKey)
      if (idxFrom < 0 || idxTo < 0) return p
      const next = [...p.order]
      next.splice(idxFrom, 1)
      next.splice(idxTo, 0, fromKey)
      return { ...p, order: next }
    })
  }, [])

  const reset = useCallback(() => {
    setProfile(buildDefaultProfile(defaultsRef.current))
  }, [])

  const visibleColumns = useMemo(
    () => profile.order.filter((k) => profile.visibility[k]),
    [profile.order, profile.visibility],
  )

  return {
    order: profile.order,
    visibility: profile.visibility,
    visibleColumns,
    setVisibility,
    toggleVisibility,
    setOrder,
    moveColumn,
    reset,
    all: defaults,
  }
}
