import { describe, it, expect, beforeEach } from 'vitest'
import { useMatrixStore } from '../matrix-store'

describe('entity update stamp (FOUND-03)', () => {
  beforeEach(() => {
    useMatrixStore.setState({
      entityUpdateStamp: {},
    })
  })

  it("initial entityUpdateStamp is {}", () => {
    const state = useMatrixStore.getState()
    expect(state.entityUpdateStamp).toEqual({})
  })

  it("notifyEntityUpdated('articles') increments entityUpdateStamp for articles", () => {
    const { notifyEntityUpdated } = useMatrixStore.getState()
    notifyEntityUpdated('articles')
    const state = useMatrixStore.getState()
    expect(state.entityUpdateStamp['articles']).toBe(1)
  })

  it("entityUpdateStamp is scoped per entity — articles stamp does not affect products", () => {
    const { notifyEntityUpdated } = useMatrixStore.getState()
    notifyEntityUpdated('articles')
    const state = useMatrixStore.getState()
    expect(state.entityUpdateStamp['articles']).toBe(1)
    expect(state.entityUpdateStamp['products']).toBeUndefined()
  })

  it("multiple notifyEntityUpdated calls increment monotonically", () => {
    const { notifyEntityUpdated } = useMatrixStore.getState()
    notifyEntityUpdated('articles')
    notifyEntityUpdated('articles')
    const state = useMatrixStore.getState()
    expect(state.entityUpdateStamp['articles']).toBe(2)
  })
})
