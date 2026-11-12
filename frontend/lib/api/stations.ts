import { CLIENT_STATIONS_URL } from "@/lib/api/config"
import { ApiError, extractErrorMessage, fetchJson } from "@/lib/api/http"
import type { Location } from "@/lib/locations"

export interface StationsResponse {
  source: "express"
  path: string
  count: number
  locations: Location[]
}

export async function fetchStationsFromExpress(): Promise<StationsResponse> {
  const data = await fetchJson(CLIENT_STATIONS_URL, { method: "GET", cache: "no-store" })
  if (!data || typeof data !== "object") {
    throw new ApiError("充電站 API 回傳格式不正確")
  }
  const rec = data as Record<string, unknown>
  if (rec.error) {
    throw new ApiError(extractErrorMessage(data) || "讀取充電站失敗")
  }
  const locations = Array.isArray(rec.locations) ? (rec.locations as Location[]) : []
  if (locations.length === 0) {
    throw new ApiError("Express 沒有回傳任何充電站")
  }
  return {
    source: "express",
    path: typeof rec.path === "string" ? rec.path : "",
    count: locations.length,
    locations,
  }
}
