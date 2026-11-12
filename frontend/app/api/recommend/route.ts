import { NextResponse } from "next/server"
import { fetchFastApiRecommendationsRaw, type RecommendPayload } from "@/lib/api/backend-proxy"
import { mapRecommendResponse } from "@/lib/api/normalize"
import { ApiError } from "@/lib/api/http"
import { rankStationsWithTopsis } from "@/lib/ai/recommend-stations"

function readNumber(value: unknown): number | undefined {
  const n = Number(value)
  return Number.isFinite(n) ? n : undefined
}

function readStations(raw: unknown): RecommendPayload["stations"] {
  if (!Array.isArray(raw)) return undefined
  const rows: NonNullable<RecommendPayload["stations"]> = []
  for (const item of raw) {
    if (!item || typeof item !== "object") continue
    const rec = item as Record<string, unknown>
    const lat = readNumber(rec.lat ?? rec.latitude)
    const lng = readNumber(rec.lng ?? rec.lon ?? rec.longitude)
    const id = rec.id != null ? String(rec.id) : rec.StationID != null ? String(rec.StationID) : ""
    const name = rec.station_name != null ? String(rec.station_name) : rec.name != null ? String(rec.name) : id
    if (!id || lat == null || lng == null) continue
    rows.push({
      id,
      name,
      lat,
      lng,
      cost: readNumber(rec.cost ?? rec.price),
      available: readNumber(rec.available ?? rec.available_points),
      poi_count: readNumber(rec.poi_count),
    })
  }
  return rows.length > 0 ? rows : undefined
}

export async function POST(request: Request) {
  try {
    const body = (await request.json()) as Record<string, unknown>
    const lat = readNumber(body.lat ?? body.latitude)
    const lng = readNumber(body.lng ?? body.longitude)
    const batteryPercent = readNumber(
      body.batteryPercent ?? body.battery_percent ?? body.battery ?? body.soc
    )
    const departureTime =
      typeof body.departureTime === "string"
        ? body.departureTime
        : typeof body.departure_time === "string"
          ? body.departure_time
          : undefined
    const destination =
      typeof body.destination === "string" && body.destination.trim()
        ? body.destination.trim()
        : undefined
    const isAvailableNow = Boolean(body.isAvailableNow ?? body.is_available_now)
    const stations = readStations(body.stations)

    if (lat == null || lng == null || batteryPercent == null) {
      return NextResponse.json(
        { error: "請提供 lat、lng 與 batteryPercent" },
        { status: 400 }
      )
    }

    const payload: RecommendPayload = {
      lat,
      lng,
      batteryPercent,
      departureTime,
      destination,
      stations,
      isAvailableNow,
    }

    try {
      const { data, path } = await fetchFastApiRecommendationsRaw(payload)
      const items = mapRecommendResponse(data)
      if (items.length > 0) {
        return NextResponse.json({
          source: "fastapi",
          path,
          count: items.length,
          items,
        })
      }
    } catch (error) {
      if (!stations?.length) {
        const message = error instanceof Error ? error.message : "取得推薦失敗"
        const status = error instanceof ApiError && error.status >= 400 ? error.status : 502
        return NextResponse.json({ error: message }, { status })
      }
    }

    const items = rankStationsWithTopsis(
      (stations ?? []).map((station) => ({
        id: station.id,
        name: station.name,
        lat: station.lat,
        lng: station.lng,
        cost: station.cost,
        available: station.available,
        poiCount: station.poi_count,
      })),
      { lat, lng },
      batteryPercent,
      isAvailableNow
    )

    return NextResponse.json({
      source: "local_topsis",
      path: "lib/ai/recommend-stations",
      count: items.length,
      items,
    })
  } catch (error) {
    const message = error instanceof Error ? error.message : "取得推薦失敗"
    const status = error instanceof ApiError && error.status >= 400 ? error.status : 502
    return NextResponse.json({ error: message }, { status })
  }
}
