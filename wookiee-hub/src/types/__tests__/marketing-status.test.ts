import { describe, it, expect } from 'vitest'
import { STATUS_UI_TO_DB, STATUS_DB_TO_UI, STATUS_LABELS, STATUS_COLORS } from '../marketing'

describe('Status mappings', () => {
  it('round-trips UI→DB→UI', () => {
    expect(STATUS_DB_TO_UI[STATUS_UI_TO_DB.active]).toBe('active')
    expect(STATUS_DB_TO_UI[STATUS_UI_TO_DB.free]).toBe('free')
    expect(STATUS_DB_TO_UI[STATUS_UI_TO_DB.archive]).toBe('archive')
  })

  it('maps free→paused, archive→archived', () => {
    expect(STATUS_UI_TO_DB.free).toBe('paused')
    expect(STATUS_UI_TO_DB.archive).toBe('archived')
    expect(STATUS_UI_TO_DB.active).toBe('active')
  })

  it('exposes Russian labels per v4', () => {
    expect(STATUS_LABELS.active).toBe('Используется')
    expect(STATUS_LABELS.free).toBe('Свободен')
    expect(STATUS_LABELS.archive).toBe('Архив')
  })

  it('exposes badge colors per v4', () => {
    expect(STATUS_COLORS.active).toBe('green')
    expect(STATUS_COLORS.free).toBe('blue')
    expect(STATUS_COLORS.archive).toBe('gray')
  })
})
