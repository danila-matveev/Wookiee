import { describe, it, expect, beforeEach } from 'vitest'
import { useMatrixStore } from '../matrix-store'

describe('detail panel routing (FOUND-02)', () => {
  beforeEach(() => {
    useMatrixStore.setState({
      detailPanelId: null,
      detailPanelEntityType: null,
    })
  })

  it("openDetailPanel(id, 'articles') sets detailPanelEntityType to 'articles'", () => {
    const { openDetailPanel } = useMatrixStore.getState()
    openDetailPanel(42, 'articles')
    const state = useMatrixStore.getState()
    expect(state.detailPanelId).toBe(42)
    expect(state.detailPanelEntityType).toBe('articles')
  })

  it("openDetailPanel(id) without entityType leaves detailPanelEntityType unchanged", () => {
    useMatrixStore.setState({ detailPanelEntityType: 'models' })
    const { openDetailPanel } = useMatrixStore.getState()
    openDetailPanel(99)
    const state = useMatrixStore.getState()
    expect(state.detailPanelId).toBe(99)
    expect(state.detailPanelEntityType).toBe('models')
  })

  it("closeDetailPanel resets both detailPanelId and detailPanelEntityType to null", () => {
    const { openDetailPanel, closeDetailPanel } = useMatrixStore.getState()
    openDetailPanel(1, 'products')
    closeDetailPanel()
    const state = useMatrixStore.getState()
    expect(state.detailPanelId).toBeNull()
    expect(state.detailPanelEntityType).toBeNull()
  })

  it("opening panel with different entityType updates detailPanelEntityType", () => {
    const { openDetailPanel } = useMatrixStore.getState()
    openDetailPanel(1, 'models')
    openDetailPanel(2, 'articles')
    const state = useMatrixStore.getState()
    expect(state.detailPanelId).toBe(2)
    expect(state.detailPanelEntityType).toBe('articles')
  })
})
