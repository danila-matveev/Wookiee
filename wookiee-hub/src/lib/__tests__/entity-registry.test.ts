import { describe, it, expect } from 'vitest'
import { ENTITY_REGISTRY, getBackendType, getEntityLabel } from '@/lib/entity-registry'
import type { EntityRegistryEntry } from '@/lib/entity-registry'

describe('entity-registry', () => {
  describe('getBackendType', () => {
    it('maps models to modeli_osnova', () => {
      expect(getBackendType('models')).toBe('modeli_osnova')
    })
    it('maps articles to artikuly', () => {
      expect(getBackendType('articles')).toBe('artikuly')
    })
    it('maps products to tovary', () => {
      expect(getBackendType('products')).toBe('tovary')
    })
    it('maps colors to cveta', () => {
      expect(getBackendType('colors')).toBe('cveta')
    })
    it('maps factories to fabriki', () => {
      expect(getBackendType('factories')).toBe('fabriki')
    })
    it('maps importers to importery', () => {
      expect(getBackendType('importers')).toBe('importery')
    })
    it('maps cards-wb to skleyki_wb', () => {
      expect(getBackendType('cards-wb')).toBe('skleyki_wb')
    })
    it('maps cards-ozon to skleyki_ozon', () => {
      expect(getBackendType('cards-ozon')).toBe('skleyki_ozon')
    })
    it('maps certs to sertifikaty', () => {
      expect(getBackendType('certs')).toBe('sertifikaty')
    })
  })

  describe('getEntityLabel', () => {
    it('returns Russian label for models', () => {
      expect(getEntityLabel('models')).toBe('Модели')
    })
    it('returns Russian label for articles', () => {
      expect(getEntityLabel('articles')).toBe('Артикулы')
    })
    it('returns Russian label for products', () => {
      expect(getEntityLabel('products')).toBe('Товары')
    })
  })

  describe('ENTITY_REGISTRY', () => {
    const ALL_SLUGS = [
      'models', 'articles', 'products', 'colors',
      'factories', 'importers', 'cards-wb', 'cards-ozon', 'certs',
    ] as const

    it('contains all 9 entity slugs', () => {
      for (const slug of ALL_SLUGS) {
        expect(ENTITY_REGISTRY[slug]).toBeDefined()
      }
    })

    it('each entry has backendType, label, and titleField', () => {
      for (const slug of ALL_SLUGS) {
        const entry: EntityRegistryEntry = ENTITY_REGISTRY[slug]
        expect(entry.backendType).toBeTruthy()
        expect(entry.label).toBeTruthy()
        expect(entry.titleField).toBeTruthy()
      }
    })
  })
})
