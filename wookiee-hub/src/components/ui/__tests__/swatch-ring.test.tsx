import { render, screen } from "@testing-library/react"
import { describe, it, expect } from "vitest"
import { ColorSwatch } from "../color-swatch"
import { Ring } from "../ring"

describe("ColorSwatch", () => {
  it("renders with hex color", () => {
    const { container } = render(<ColorSwatch color="#FF0000" />)
    const sw = container.querySelector('[data-slot="color-swatch"]') as HTMLElement
    expect(sw).not.toBeNull()
    expect(sw.style.backgroundColor).toBe("rgb(255, 0, 0)")
  })
})

describe("Ring", () => {
  it("renders progress ring with value", () => {
    render(<Ring value={75} max={100} />)
    expect(screen.getByText("75%")).toBeInTheDocument()
  })
})
