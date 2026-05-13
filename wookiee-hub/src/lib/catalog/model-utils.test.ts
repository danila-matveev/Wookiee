import { describe, expect, it } from "vitest"

import { parseRazmeryModeli } from "./model-utils"

describe("parseRazmeryModeli (W9.8)", () => {
  it("returns empty array for null/undefined/blank", () => {
    expect(parseRazmeryModeli(null)).toEqual([])
    expect(parseRazmeryModeli(undefined)).toEqual([])
    expect(parseRazmeryModeli("")).toEqual([])
    expect(parseRazmeryModeli("   ")).toEqual([])
  })

  it("parses comma-separated CSV (Ruby — реальный кейс из W9.8)", () => {
    // Ruby в БД: razmery_modeli = "S, M, L" (3 размера, не 4 — фикс bug W9.8)
    expect(parseRazmeryModeli("S, M, L")).toEqual(["S", "M", "L"])
  })

  it("parses with various delimiters (comma, semicolon, whitespace)", () => {
    expect(parseRazmeryModeli("S;M;L")).toEqual(["S", "M", "L"])
    expect(parseRazmeryModeli("S M L")).toEqual(["S", "M", "L"])
    expect(parseRazmeryModeli("S , M , L")).toEqual(["S", "M", "L"])
  })

  it("parses JSON array form", () => {
    expect(parseRazmeryModeli('["S","M","L"]')).toEqual(["S", "M", "L"])
    expect(parseRazmeryModeli('["XS", "S", "M", "L", "XL"]')).toEqual([
      "XS",
      "S",
      "M",
      "L",
      "XL",
    ])
  })

  it("falls back to CSV when JSON parse fails", () => {
    expect(parseRazmeryModeli("[broken")).toEqual(["[broken"])
  })

  it("drops empty fragments from trailing/double commas", () => {
    expect(parseRazmeryModeli("S,,M,L,")).toEqual(["S", "M", "L"])
  })
})
