import {
  EXPRESS_API_URL,
  EXPRESS_BACKEND_URL,
  EXPRESS_STATIONS_PATHS,
  FASTAPI_RECOMMEND_PATHS,
  FASTAPI_URL,
} from "@/lib/api/config"
import { ApiError, fetchJson } from "@/lib/api/http"

const pathCache: { stations?: string; recommend?: string } = {}

export interface RecommendPayload {
  lat: number
  lng: number
  batteryPercent: number
  departureTime?: string
  destination?: string
  isAvailableNow?: boolean
  stations?: Array<{
    id: string
    name: string
    lat: number
    lng: number
    cost?: number
    available?: number
    poi_count?: number
  }>
}

function joinUrl(base: string, path: string): string {
  const normalizedBase = (base || "").replace(/\/$/, "")
  const normalizedPath = path.startsWith("/") ? path : `/${path}`
  return `${normalizedBase}${normalizedPath}`
}

export async function fetchExpressStationsRaw(): Promise<{ data: unknown; path: string }> {
  const expressBase = EXPRESS_API_URL || EXPRESS_BACKEND_URL || "http://localhost:5000"
  const paths = pathCache.stations
    ? [pathCache.stations, ...EXPRESS_STATIONS_PATHS.filter((p) => p !== pathCache.stations)]
    : EXPRESS_STATIONS_PATHS

  const errors: string[] = []
  for (const path of paths) {
    try {
      const data = await fetchJson(joinUrl(expressBase, path), { method: "GET", cache: "no-store" }, 30000)
      pathCache.stations = path
      return { data, path }
    } catch (error) {
      const message = error instanceof ApiError ? error.message : String(error)
      errors.push(`${path} → ${message}`)
    }
  }

  throw new ApiError(
    `無法從 Express (${expressBase}) 取得充電站列表。請確認服務已啟動。${errors[0] ? ` 最後錯誤：${errors[0]}` : ""}`,
    502
  )
}

function recommendBodies(payload: RecommendPayload): unknown[] {
  const { lat, lng, batteryPercent, departureTime, destination, stations, isAvailableNow } = payload
  const shared = {
    lat,
    lng,
    battery_percent: batteryPercent,
    departure_time: departureTime,
    destination,
    is_available_now: Boolean(isAvailableNow),
    stations,
  }
  return [
    shared,
    {
      latitude: lat,
      longitude: lng,
      battery: batteryPercent,
      departure_time: departureTime,
      destination,
      stations,
    },
    {
      current_location: { lat, lng },
      soc: batteryPercent,
      departure_time: departureTime,
      destination,
    },
    {
      user_lat: lat,
      user_lng: lng,
      remaining_battery: batteryPercent,
      destination,
    },
  ]
}

export async function fetchFastApiRecommendationsRaw(
  payload: RecommendPayload
): Promise<{ data: unknown; path: string }> {
  const fastapiBase = FASTAPI_URL || "http://127.0.0.1:8000"
  const paths = pathCache.recommend
    ? [pathCache.recommend, ...FASTAPI_RECOMMEND_PATHS.filter((p) => p !== pathCache.recommend)]
    : FASTAPI_RECOMMEND_PATHS

  const bodies = recommendBodies(payload)
  const errors: string[] = []

  for (const path of paths) {
    for (const body of bodies) {
      try {
        const data = await fetchJson(
          joinUrl(fastapiBase, path),
          {
            method: "POST",
            body: JSON.stringify(body),
          },
          30000
        )
        pathCache.recommend = path
        return { data, path }
      } catch (error) {
        const status = error instanceof ApiError ? error.status : 0
        const message = error instanceof ApiError ? error.message : String(error)
        errors.push(`${path} → ${message}`)
        if (status === 404) break
      }
    }
  }

  throw new ApiError(
    `無法從 FastAPI (${fastapiBase}) 取得推薦。請確認服務已啟動。${errors[0] ? ` 最後錯誤：${errors[0]}` : ""}`,
    502
  )
}
