import { describe, it } from 'vitest'

describe('entity update stamp (FOUND-03)', () => {
  it.todo("notifyEntityUpdated('articles') increments entityUpdateStamp for articles")
  it.todo("entityUpdateStamp is scoped per entity — articles stamp does not affect products")
  it.todo("initial entityUpdateStamp is 0 for all entities")
  it.todo("multiple notifyEntityUpdated calls increment monotonically")
})
