import { describe, expect, it } from "vitest"
import { rankStationsWithTopsis, type StationRankInput } from "@/lib/ai/recommend-stations"
import { haversineKm } from "@/lib/map-coords"

const taipei101 = { lat: 25.033, lng: 121.5654 }

const stations: StationRankInput[] = [
  { id: "near", name: "Near", lat: 25.034, lng: 121.566, cost: 8, available: 3 },
  { id: "full", name: "Full", lat: 25.0335, lng: 121.565, cost: 0, available: 0 },
  { id: "mid", name: "Mid", lat: 25.045, lng: 121.575, cost: 12, available: 1 },
  { id: "taichung", name: "Taichung", lat: 24.1477, lng: 120.6736, cost: 5, available: 8 },
]

describe("haversineKm", () => {
  it("is ~130 km from Taipei Main Station to Taichung Station", () => {
    const d = haversineKm({ lat: 25.0478, lng: 121.517 }, { lat: 24.1369, lng: 120.6855 })
    expect(d).toBeGreaterThan(125)
    expect(d).toBeLessThan(135)
  })
})

describe("rankStationsWithTopsis", () => {
  it("drops out-of-range and fully occupied stations at low battery", () => {
    const ids = rankStationsWithTopsis(stations, taipei101, 10).map((r) => r.id)
    expect(ids).not.toContain("taichung")
    expect(ids).not.toContain("full")
    expect(ids[0]).toBe("near")
  })

  it("numbers results 1..n and includes a readable reason", () => {
    const ranked = rankStationsWithTopsis(stations, taipei101, 100)
    expect(ranked.map((r) => r.rank)).toEqual(ranked.map((_, i) => i + 1))
    expect(ranked[0].reason).toMatch(/HIGH BATTERY · TOPSIS \d\.\d{3} · \d+\.\d km/)
  })

  it("respects maxCandidates", () => {
    expect(rankStationsWithTopsis(stations, taipei101, 100, false, 2)).toHaveLength(2)
  })

  it("still returns the closest stations when nothing is reachable", () => {
    const ranked = rankStationsWithTopsis(stations, taipei101, 0)
    expect(ranked.length).toBeGreaterThan(0)
  })
})
