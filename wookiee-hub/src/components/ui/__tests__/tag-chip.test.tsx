import { render, screen, fireEvent } from "@testing-library/react"
import { describe, it, expect, vi } from "vitest"
import { Tag } from "../tag"
import { Chip } from "../chip"

describe("Tag", () => {
  it("renders text", () => {
    render(<Tag>premium</Tag>)
    expect(screen.getByText("premium")).toBeInTheDocument()
  })
})

describe("Chip", () => {
  it("renders with onRemove", () => {
    const onRemove = vi.fn()
    render(<Chip onRemove={onRemove}>Filter: status=active</Chip>)
    fireEvent.click(screen.getByRole("button"))
    expect(onRemove).toHaveBeenCalled()
  })
})
