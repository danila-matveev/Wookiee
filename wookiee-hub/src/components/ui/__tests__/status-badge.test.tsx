import { render, screen } from "@testing-library/react"
import { describe, it, expect } from "vitest"
import { StatusBadge } from "../status-badge"

describe("StatusBadge", () => {
  it("renders 'active' status as emerald", () => {
    render(<StatusBadge status="active" />)
    const el = screen.getByText(/Активен/i)
    expect(el.className).toMatch(/emerald/)
  })

  it("renders 'archived' status as gray", () => {
    render(<StatusBadge status="archived" />)
    const el = screen.getByText(/Архив/i)
    expect(el.className).toMatch(/stone|gray/)
  })
})
