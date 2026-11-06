import { describe, expect, it } from "vitest"
import { topsisRank, type TopsisCandidate } from "@/lib/ai/topsis"

const s = (id: string, distance: number, cost: number, availablePots: number, poiCount = 0): TopsisCandidate => ({
  id,
  distance,
  cost,
  availablePots,
  poiCount,
})

describe("topsisRank", () => {
  it("returns [] for no stations", () => {
    expect(topsisRank([], 0.5, false)).toEqual([])
  })

  it("puts a station that dominates on every criterion first with score 1", () => {
    const ranked = topsisRank([s("worst", 5000, 12, 1, 0), s("best", 500, 6, 4, 5)], 0.5, false)
    expect(ranked[0].id).toBe("best")
    expect(ranked[0].topsisScore).toBeCloseTo(1)
    expect(ranked[1].topsisScore).toBeCloseTo(0)
  })

  it("returns scores in [0,1], sorted best-first", () => {
    const stations = Array.from({ length: 10 }, (_, i) => s(String(i), 1000 * (i + 1), 5 + (i % 3), i % 4, i % 2))
    const scores = topsisRank(stations, 0.3, false).map((r) => r.topsisScore)
    expect(scores.every((x) => x >= 0 && x <= 1)).toBe(true)
    expect(scores).toEqual([...scores].sort((a, b) => b - a))
  })

  it("gives identical stations a neutral 0.5", () => {
    const ranked = topsisRank([s("a", 1000, 8, 2), s("b", 1000, 8, 2)], 0.5, false)
    expect(ranked.map((r) => r.topsisScore)).toEqual([0.5, 0.5])
  })

  it("lets the battery level change the winner", () => {
    const near = s("near", 500, 20, 2)
    const far = s("far", 8000, 2, 2)
    expect(topsisRank([near, far], 0.05, false)[0].id).toBe("near")
    expect(topsisRank([near, far], 0.95, false)[0].id).toBe("far")
  })

  it("never ranks a full station first for an urgent user, and keeps the original distance", () => {
    const ranked = topsisRank([s("full", 100, 1, 0), s("free", 4000, 15, 1)], 0.5, true)
    expect(ranked[0].id).toBe("free")
    expect(ranked.find((r) => r.id === "full")!.distance).toBe(100)
  })
})
