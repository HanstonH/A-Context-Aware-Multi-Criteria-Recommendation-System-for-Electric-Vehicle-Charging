import { describe, expect, it } from "vitest"
import { mapRecommendResponse } from "@/lib/api/normalize"

describe("mapRecommendResponse", () => {
  it("maps the FastAPI /recommend payload to RecommendItems", () => {
    const payload = {
      recommendations: [
        { StationID: "S1", station_name: "Alpha", lat: 25.03, lon: 121.56, distance: 1500, topsis_score: 0.91 },
        { StationID: "S2", station_name: "Beta", lat: 25.04, lon: 121.57, distance: 3200, topsis_score: 0.42 },
      ],
    }
    const items = mapRecommendResponse(payload)
    expect(items).toHaveLength(2)
    expect(items[0]).toMatchObject({ id: "S1", name: "Alpha", rank: 1, score: 0.91, lat: 25.03, lng: 121.56 })
    expect(items[0].distanceKm).toBeCloseTo(1.5) // metres -> km
    expect(items[1].rank).toBe(2)
  })

  it("returns [] for garbage input", () => {
    expect(mapRecommendResponse(null)).toEqual([])
    expect(mapRecommendResponse("oops")).toEqual([])
    expect(mapRecommendResponse({})).toEqual([])
  })
})
