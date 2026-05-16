import { render, screen } from "@testing-library/react"
import { describe, it, expect } from "vitest"
import { Skeleton } from "../skeleton"
import { Kbd } from "../kbd"
import { EmptyState } from "../empty-state"

describe("Skeleton", () => {
  it("renders with width and height", () => {
    const { container } = render(<Skeleton className="h-4 w-32" />)
    expect(container.firstChild).toHaveClass("h-4")
  })
})

describe("Kbd", () => {
  it("renders single key", () => {
    render(<Kbd>⌘</Kbd>)
    expect(screen.getByText("⌘")).toBeInTheDocument()
  })

  it("renders combo array", () => {
    render(<Kbd keys={["⌘", "K"]} />)
    expect(screen.getByText("⌘")).toBeInTheDocument()
    expect(screen.getByText("K")).toBeInTheDocument()
  })
})

describe("EmptyState", () => {
  it("renders title and description", () => {
    render(<EmptyState title="Нет данных" description="Пока пусто" />)
    expect(screen.getByText("Нет данных")).toBeInTheDocument()
    expect(screen.getByText("Пока пусто")).toBeInTheDocument()
  })
})
