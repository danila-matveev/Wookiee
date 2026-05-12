import { useCallback, useEffect, useMemo, useState } from "react"

import type { CatalogColumnDef } from "@/components/catalog/ui/column-config"

/**
 * useColumnConfig — состояние конфигуратора колонок реестра каталога (W9.5).
 *
 * Хранит `visibility` (карта показано/скрыто по ключу) + `order` (массив ключей
 * в выбранном пользователем порядке) в localStorage по ключу
 * `catalog-<pageKey>-columns-v2`.
 *
 * Возвращает `visibleColumns` — список `CatalogColumnDef` в текущем порядке,
 * отфильтрованный по видимости. Это значение и нужно проходить в map() при
 * рендере шапки и тела таблицы.
 *
 * Внутри:
 * - При первом монтировании читает localStorage; если значения нет/невалидное —
 *   использует `defaults`, посчитанные из `defaultColumns`.
 * - Новые колонки, добавленные в `defaultColumns` после сохранения, считаются
 *   видимыми/скрытыми согласно их `default` и добавляются в конец `order`.
 */
export type CatalogPageKey =
  | "matrix"
  | "matrix-artikuly"
  | "matrix-tovary"
  | "artikuly"
  | "tovary"

interface StoredConfig {
  visibility: Record<string, boolean>
  order: string[]
}

interface UseColumnConfigResult {
  /** Колонки в порядке отображения, только видимые. Используйте в map() рендера. */
  visibleColumns: CatalogColumnDef[]
  /** Карта видимости (включая скрытые). */
  visibility: Record<string, boolean>
  /** Текущий порядок ключей (включая скрытые — они в конце или сохраняют позицию). */
  order: string[]
  /** Применить новое состояние. */
  setConfig: (next: { visibility: Record<string, boolean>; order: string[] }) => void
  /** Сбросить к defaults. */
  reset: () => void
}

const STORAGE_PREFIX = "catalog-"
const STORAGE_SUFFIX = "-columns-v2"

function storageKey(pageKey: CatalogPageKey): string {
  return `${STORAGE_PREFIX}${pageKey}${STORAGE_SUFFIX}`
}

function buildDefaults(defaultColumns: CatalogColumnDef[]): StoredConfig {
  const visibility: Record<string, boolean> = {}
  const order: string[] = []
  // Default ordering: default-visible first (in registry order), then default-hidden.
  for (const c of defaultColumns) if (c.default) order.push(c.key)
  for (const c of defaultColumns) if (!c.default) order.push(c.key)
  for (const c of defaultColumns) visibility[c.key] = c.default
  return { visibility, order }
}

function readStored(pageKey: CatalogPageKey): StoredConfig | null {
  if (typeof window === "undefined") return null
  try {
    const raw = window.localStorage.getItem(storageKey(pageKey))
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<StoredConfig>
    if (!parsed || typeof parsed !== "object") return null
    if (!Array.isArray(parsed.order) || !parsed.order.every((x) => typeof x === "string")) return null
    if (!parsed.visibility || typeof parsed.visibility !== "object") return null
    return {
      visibility: parsed.visibility as Record<string, boolean>,
      order: parsed.order as string[],
    }
  } catch {
    return null
  }
}

function writeStored(pageKey: CatalogPageKey, cfg: StoredConfig): void {
  if (typeof window === "undefined") return
  try {
    window.localStorage.setItem(storageKey(pageKey), JSON.stringify(cfg))
  } catch {
    // QuotaExceeded / private mode → silent fallback
  }
}

/**
 * Merge persisted config с актуальным реестром колонок.
 * - Если в `defaultColumns` есть новые ключи (не было при сохранении), добавляем их
 *   в конец order и в visibility согласно their `default`.
 * - Если в сохранённой версии есть «мёртвые» ключи (колонка удалена из реестра) —
 *   убираем их из order/visibility.
 */
function reconcile(
  stored: StoredConfig,
  defaultColumns: CatalogColumnDef[],
): StoredConfig {
  const knownKeys = new Set(defaultColumns.map((c) => c.key))
  const order = stored.order.filter((k) => knownKeys.has(k))
  const visibility: Record<string, boolean> = {}
  for (const k of order) visibility[k] = stored.visibility[k] !== false
  for (const c of defaultColumns) {
    if (!order.includes(c.key)) {
      order.push(c.key)
      visibility[c.key] = c.default
    }
    // Сохраняем явный false (скрыта), но если в stored нет ключа — берём default.
    if (visibility[c.key] === undefined) visibility[c.key] = c.default
  }
  return { visibility, order }
}

export function useColumnConfig(
  pageKey: CatalogPageKey,
  defaultColumns: CatalogColumnDef[],
): UseColumnConfigResult {
  const defaults = useMemo(() => buildDefaults(defaultColumns), [defaultColumns])

  const [state, setState] = useState<StoredConfig>(() => {
    const stored = readStored(pageKey)
    if (!stored) return defaults
    return reconcile(stored, defaultColumns)
  })

  // If `defaultColumns` reference changes mid-session (rare), re-reconcile.
  // (Шапка с pageKey не меняется в рамках жизни страницы, но колонки могут
  // прийти позже с лейблами зависящими от i18n/feature flags.)
  useEffect(() => {
    setState((prev) => reconcile(prev, defaultColumns))
  }, [defaultColumns])

  const persist = useCallback((next: StoredConfig) => {
    setState(next)
    writeStored(pageKey, next)
  }, [pageKey])

  const setConfig = useCallback(
    (next: { visibility: Record<string, boolean>; order: string[] }) => {
      persist({ visibility: next.visibility, order: next.order })
    },
    [persist],
  )

  const reset = useCallback(() => {
    persist(defaults)
  }, [persist, defaults])

  const visibleColumns = useMemo<CatalogColumnDef[]>(() => {
    const byKey = new Map(defaultColumns.map((c) => [c.key, c]))
    const list: CatalogColumnDef[] = []
    for (const k of state.order) {
      const col = byKey.get(k)
      if (!col) continue
      const visible = state.visibility[k]
      if (visible === false) continue
      list.push(col)
    }
    return list
  }, [defaultColumns, state])

  return {
    visibleColumns,
    visibility: state.visibility,
    order: state.order,
    setConfig,
    reset,
  }
}
