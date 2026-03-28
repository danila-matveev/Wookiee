import type { MatrixEntity } from '@/stores/matrix-store'

// Re-export for external consumers
export type EntitySlug = MatrixEntity

export interface EntityRegistryEntry {
  backendType: string
  label: string
  titleField: string
}

/**
 * Single source of truth for entity slug → backend type mappings.
 * Replaces ENTITY_TYPE_MAP, ENTITY_TO_DB, and ENTITY_BACKEND_MAP.
 * All backendType values use plural forms (matching the backend API convention).
 */
export const ENTITY_REGISTRY: Record<MatrixEntity, EntityRegistryEntry> = {
  models: {
    backendType: 'modeli_osnova',
    label: 'Модели',
    titleField: 'kod',
  },
  articles: {
    backendType: 'artikuly',
    label: 'Артикулы',
    titleField: 'artikul',
  },
  products: {
    backendType: 'tovary',
    label: 'Товары',
    titleField: 'artikul_ozon',
  },
  colors: {
    backendType: 'cveta',
    label: 'Цвета',
    titleField: 'nazvanie',
  },
  factories: {
    backendType: 'fabriki',
    label: 'Фабрики',
    titleField: 'nazvanie',
  },
  importers: {
    backendType: 'importery',
    label: 'Импортеры',
    titleField: 'nazvanie',
  },
  'cards-wb': {
    backendType: 'skleyki_wb',
    label: 'Карточки WB',
    titleField: 'nazvanie',
  },
  'cards-ozon': {
    backendType: 'skleyki_ozon',
    label: 'Карточки Ozon',
    titleField: 'nazvanie',
  },
  certs: {
    backendType: 'sertifikaty',
    label: 'Сертификаты',
    titleField: 'nomer',
  },
}

/**
 * Returns the plural backend entity type for a given frontend slug.
 * Use this for API calls: /api/matrix/:backendType/...
 */
export function getBackendType(slug: MatrixEntity): string {
  return ENTITY_REGISTRY[slug].backendType
}

/**
 * Returns the Russian display label for a given frontend slug.
 */
export function getEntityLabel(slug: MatrixEntity): string {
  return ENTITY_REGISTRY[slug].label
}
