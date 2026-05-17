import { render, screen } from "@testing-library/react"
import { describe, it, expect } from "vitest"
import { Button } from "../button"

describe("Button extended variants", () => {
  it("success variant renders emerald", () => {
    render(<Button variant="success">OK</Button>)
    expect(screen.getByRole("button").className).toMatch(/emerald/)
  })

  it("danger-ghost variant renders red text", () => {
    render(<Button variant="danger-ghost">Delete</Button>)
    expect(screen.getByRole("button").className).toMatch(/red/)
  })
})
