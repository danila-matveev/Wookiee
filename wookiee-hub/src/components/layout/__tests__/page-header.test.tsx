import { render, screen } from "@testing-library/react"
import { describe, it, expect } from "vitest"
import { MemoryRouter } from "react-router-dom"
import { PageHeader } from "../page-header"

describe("PageHeader", () => {
  it("renders title in Instrument Serif italic", () => {
    render(
      <MemoryRouter>
        <PageHeader title="Тестовая страница" />
      </MemoryRouter>
    )
    const h1 = screen.getByRole("heading", { level: 1, name: "Тестовая страница" })
    expect(h1.style.fontFamily).toMatch(/Instrument Serif/i)
    expect(h1.className).toMatch(/italic/)
  })

  it("renders kicker and description", () => {
    render(
      <MemoryRouter>
        <PageHeader kicker="Раздел" title="T" description="opis" />
      </MemoryRouter>
    )
    expect(screen.getByText("Раздел")).toBeInTheDocument()
    expect(screen.getByText("opis")).toBeInTheDocument()
  })

  it("renders breadcrumbs", () => {
    render(
      <MemoryRouter>
        <PageHeader
          title="T"
          breadcrumbs={[
            { label: "Home", to: "/" },
            { label: "Operations", to: "/operations" },
          ]}
        />
      </MemoryRouter>
    )
    expect(screen.getByText("Home")).toBeInTheDocument()
    expect(screen.getByText("Operations")).toBeInTheDocument()
  })
})
