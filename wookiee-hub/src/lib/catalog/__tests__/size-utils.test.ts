import { describe, it, expect } from "vitest"
import { compareRazmer, RAZMER_LADDER, razmerOrder } from "../size-utils"

describe("razmerOrder", () => {
  it("returns 999 for null/undefined/empty", () => {
    expect(razmerOrder(null)).toBe(999)
    expect(razmerOrder(undefined)).toBe(999)
    expect(razmerOrder("")).toBe(999)
    expect(razmerOrder("   ")).toBe(999)
  })

  it("returns 0..N for ladder letters", () => {
    expect(razmerOrder("XXS")).toBe(0)
    expect(razmerOrder("XS")).toBe(1)
    expect(razmerOrder("S")).toBe(2)
    expect(razmerOrder("M")).toBe(3)
    expect(razmerOrder("L")).toBe(4)
    expect(razmerOrder("XL")).toBe(5)
    expect(razmerOrder("XXL")).toBe(6)
    expect(razmerOrder("3XL")).toBe(7)
    expect(razmerOrder("4XL")).toBe(8)
    expect(razmerOrder("5XL")).toBe(9)
  })

  it("is case-insensitive", () => {
    expect(razmerOrder("m")).toBe(3)
    expect(razmerOrder("xl")).toBe(5)
    expect(razmerOrder("Xs")).toBe(1)
  })

  it("trims whitespace", () => {
    expect(razmerOrder("  M  ")).toBe(3)
    expect(razmerOrder("\tL\n")).toBe(4)
  })

  it("returns 100 + n for numeric sizes", () => {
    expect(razmerOrder("40")).toBe(140)
    expect(razmerOrder("42")).toBe(142)
    expect(razmerOrder("44")).toBe(144)
  })

  it("falls back to 999 for garbage", () => {
    expect(razmerOrder("XYZ")).toBe(999)
    expect(razmerOrder("???")).toBe(999)
  })

  it("places letter sizes before numeric (no overlap)", () => {
    expect(razmerOrder("5XL")).toBeLessThan(razmerOrder("40"))
  })
})

describe("compareRazmer", () => {
  it("sorts in physical order, not alpha", () => {
    const sizes = ["L", "M", "S", "XL", "XS", "XXL"]
    sizes.sort(compareRazmer)
    expect(sizes).toEqual(["XS", "S", "M", "L", "XL", "XXL"])
  })

  it("pushes unknowns to the end", () => {
    const sizes = ["M", null, "S", "???"]
    sizes.sort(compareRazmer)
    expect(sizes).toEqual(["S", "M", null, "???"])
  })

  it("interleaves letter + numeric correctly", () => {
    const sizes = ["44", "M", "40", "S"]
    sizes.sort(compareRazmer)
    expect(sizes).toEqual(["S", "M", "40", "44"])
  })
})

describe("RAZMER_LADDER", () => {
  it("exports the canonical 10-step ladder", () => {
    expect(RAZMER_LADDER).toEqual([
      "XXS", "XS", "S", "M", "L", "XL", "XXL", "3XL", "4XL", "5XL",
    ])
  })
})
