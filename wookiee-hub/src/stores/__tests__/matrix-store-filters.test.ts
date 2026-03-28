import { describe, it, expect, beforeEach } from 'vitest'
import { useMatrixStore } from '../matrix-store'

describe('matrix-store filter actions', () => {
  beforeEach(() => {
    // Reset store between tests
    useMatrixStore.setState({ activeFilters: [], activeEntity: 'models' })
  })

  it('addFilter appends new filter entry', () => {
    const { addFilter } = useMatrixStore.getState()
    addFilter({ field: 'kategoriya_id', label: 'Категория', values: [1], valueLabels: ['Бельё'] })
    expect(useMatrixStore.getState().activeFilters).toHaveLength(1)
    expect(useMatrixStore.getState().activeFilters[0].field).toBe('kategoriya_id')
  })

  it('addFilter replaces existing filter for same field (upsert)', () => {
    const { addFilter } = useMatrixStore.getState()
    addFilter({ field: 'kategoriya_id', label: 'Категория', values: [1], valueLabels: ['Бельё'] })
    addFilter({ field: 'kategoriya_id', label: 'Категория', values: [1, 5], valueLabels: ['Бельё', 'Полотенца'] })
    expect(useMatrixStore.getState().activeFilters).toHaveLength(1)
    expect(useMatrixStore.getState().activeFilters[0].values).toEqual([1, 5])
  })

  it('removeFilter removes entry by field name', () => {
    const { addFilter, removeFilter } = useMatrixStore.getState()
    addFilter({ field: 'kategoriya_id', label: 'Категория', values: [1], valueLabels: ['Бельё'] })
    addFilter({ field: 'status_id', label: 'Статус', values: [2], valueLabels: ['Архив'] })
    removeFilter('kategoriya_id')
    expect(useMatrixStore.getState().activeFilters).toHaveLength(1)
    expect(useMatrixStore.getState().activeFilters[0].field).toBe('status_id')
  })

  it('clearFilters resets to empty array', () => {
    const { addFilter, clearFilters } = useMatrixStore.getState()
    addFilter({ field: 'kategoriya_id', label: 'Категория', values: [1], valueLabels: ['Бельё'] })
    clearFilters()
    expect(useMatrixStore.getState().activeFilters).toEqual([])
  })

  it('setFilters bulk-replaces activeFilters', () => {
    const { setFilters } = useMatrixStore.getState()
    const filters = [
      { field: 'kategoriya_id', label: 'Категория', values: [1, 5], valueLabels: ['Бельё', 'Полотенца'] },
      { field: 'status_id', label: 'Статус', values: [2], valueLabels: ['Архив'] },
    ]
    setFilters(filters)
    expect(useMatrixStore.getState().activeFilters).toHaveLength(2)
    expect(useMatrixStore.getState().activeFilters).toEqual(filters)
  })

  it('setActiveEntity clears activeFilters', () => {
    const { addFilter, setActiveEntity } = useMatrixStore.getState()
    addFilter({ field: 'kategoriya_id', label: 'Категория', values: [1], valueLabels: ['Бельё'] })
    setActiveEntity('articles')
    expect(useMatrixStore.getState().activeFilters).toEqual([])
  })
})
