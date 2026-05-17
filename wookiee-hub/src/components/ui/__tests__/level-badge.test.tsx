import { render, screen } from "@testing-library/react"
import { describe, it, expect } from "vitest"
import { LevelBadge } from "../level-badge"

describe("LevelBadge", () => {
  it("renders 'model' level", () => {
    render(<LevelBadge level="model">Wendy</LevelBadge>)
    expect(screen.getByText("Wendy")).toBeInTheDocument()
  })

  it("renders 'sku' level with distinct styling", () => {
    render(<LevelBadge level="sku">SKU-123</LevelBadge>)
    const el = screen.getByText("SKU-123")
    expect(el.className).not.toBe("")
  })
})
