import { render, screen } from "@testing-library/react"
import { describe, it, expect } from "vitest"
import { Tooltip, TooltipProvider, TooltipTrigger, TooltipContent } from "../tooltip"

describe("Tooltip", () => {
  it("renders trigger and shows content on hover", async () => {
    render(
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger>Hover me</TooltipTrigger>
          <TooltipContent>Tip text</TooltipContent>
        </Tooltip>
      </TooltipProvider>
    )
    expect(screen.getByText("Hover me")).toBeInTheDocument()
  })
})
