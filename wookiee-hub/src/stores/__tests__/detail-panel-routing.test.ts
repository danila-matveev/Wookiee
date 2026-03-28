import { describe, it } from 'vitest'

describe('detail panel routing (FOUND-02)', () => {
  it.todo("openDetailPanel(id, 'articles') sets detailPanelEntityType to 'articles'")
  it.todo("openDetailPanel(id) without entityType leaves detailPanelEntityType unchanged")
  it.todo("closeDetailPanel resets both detailPanelId and detailPanelEntityType to null")
  it.todo("opening panel with different entityType updates detailPanelEntityType")
})
