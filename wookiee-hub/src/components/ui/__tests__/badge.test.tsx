import { render, screen } from "@testing-library/react"
import { describe, it, expect } from "vitest"
import { Badge } from "../badge"

describe("Badge", () => {
  it("renders with default emerald variant", () => {
    render(<Badge>Active</Badge>)
    const el = screen.getByText("Active")
    expect(el).toBeInTheDocument()
    expect(el.className).toMatch(/emerald/)
  })

  it("supports variant prop", () => {
    render(<Badge variant="red">Error</Badge>)
    const el = screen.getByText("Error")
    expect(el.className).toMatch(/red/)
  })

  it("renders dot when dot=true", () => {
    const { container } = render(<Badge dot>Live</Badge>)
    expect(container.querySelector('[data-slot="badge-dot"]')).not.toBeNull()
  })
})
