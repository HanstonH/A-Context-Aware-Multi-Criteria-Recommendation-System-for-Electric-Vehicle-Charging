import { CLIENT_RECOMMEND_URL } from "@/lib/api/config"
import { ApiError, extractErrorMessage, fetchJson } from "@/lib/api/http"
import type { RecommendItem } from "@/lib/api/normalize"

export interface RecommendRequest {
  lat: number
  lng: number
  batteryPercent: number
  departureTime?: string
  destination?: string
  stations?: Array<{
    id: string
    name: string
    lat: number
    lng: number
    cost?: number
    available?: number
    poi_count?: number
  }>
  isAvailableNow?: boolean
}

export interface RecommendResponse {
  source: "fastapi"
  path: string
  count: number
  items: RecommendItem[]
}

export async function fetchRecommendations(
  payload: RecommendRequest
): Promise<RecommendResponse> {
  const data = await fetchJson(CLIENT_RECOMMEND_URL, {
    method: "POST",
    body: JSON.stringify(payload),
  })
  if (!data || typeof data !== "object") {
    throw new ApiError("推薦 API 回傳格式不正確")
  }
  const rec = data as Record<string, unknown>
  if (rec.error) {
    throw new ApiError(extractErrorMessage(data) || "取得推薦失敗")
  }
  return {
    source: "fastapi",
    path: typeof rec.path === "string" ? rec.path : "",
    count: typeof rec.count === "number" ? rec.count : 0,
    items: Array.isArray(rec.items) ? (rec.items as RecommendItem[]) : [],
  }
}

export type { RecommendItem }
