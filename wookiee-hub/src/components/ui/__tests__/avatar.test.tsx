import { render, screen } from "@testing-library/react"
import { describe, it, expect } from "vitest"
import { Avatar } from "../avatar"
import { AvatarGroup } from "../avatar-group"

describe("Avatar", () => {
  it("renders initials when no src", () => {
    render(<Avatar name="Иван Петров" />)
    expect(screen.getByText("ИП")).toBeInTheDocument()
  })

  it("renders img when src provided", () => {
    render(<Avatar name="Test" src="https://example.com/img.png" />)
    expect(screen.getByRole("img")).toHaveAttribute("src", "https://example.com/img.png")
  })
})

describe("AvatarGroup", () => {
  it("renders multiple avatars with overlap", () => {
    const { container } = render(
      <AvatarGroup>
        <Avatar name="A B" />
        <Avatar name="C D" />
        <Avatar name="E F" />
      </AvatarGroup>
    )
    expect(container.querySelectorAll('[data-slot="avatar"]')).toHaveLength(3)
  })
})
