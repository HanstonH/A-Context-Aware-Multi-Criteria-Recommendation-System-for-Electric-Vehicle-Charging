import { BACKEND_API_KEY, BACKEND_PROXY_SECRET, BACKEND_URL } from "@/lib/api/config"
import { ApiError, fetchJson } from "@/lib/api/http"

/**
 * Server-side calls from the Next.js API routes to the shared Flask backend
 * (backend/, the same one the phone app uses).
 */

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

const STATIONS_PATH = "/api/stations"
const RECOMMEND_PATH = "/api/recommend"
// The backend returns at most 20; the web map highlights the top 10.
const RECOMMEND_LIMIT = 10

/**
 * The backend rate-limits per IP. Without this every web user would share the
 * Next.js server's IP and one busy minute would block everyone. The backend only
 * trusts X-Client-IP when it comes with the shared PROXY_SECRET.
 */
export function addClientIp(headers: Record<string, string>, clientIp?: string | null) {
  if (clientIp && BACKEND_PROXY_SECRET) {
    headers["X-Client-IP"] = clientIp
    headers["X-Proxy-Secret"] = BACKEND_PROXY_SECRET
  }
}

function backendHeaders(clientIp?: string | null): Record<string, string> {
  const headers: Record<string, string> = {}
  if (BACKEND_API_KEY) headers["X-API-Key"] = BACKEND_API_KEY
  addClientIp(headers, clientIp)
  return headers
}

/**
 * The visitor's IP. X-Real-IP is set by Railway's edge (a browser can't fake it);
 * X-Forwarded-For is only a fallback for local runs.
 */
export function clientIpFrom(request: Request): string | null {
  const real = request.headers.get("x-real-ip")?.trim()
  if (real) return real
  const fwd = request.headers.get("x-forwarded-for")
  return fwd ? fwd.split(",")[0].trim() || null : null
}

export async function fetchBackendStationsRaw(
  clientIp?: string | null
): Promise<{ data: unknown; path: string }> {
  try {
    const data = await fetchJson(
      `${BACKEND_URL}${STATIONS_PATH}`,
      { method: "GET", cache: "no-store", headers: backendHeaders(clientIp) },
      30000
    )
    return { data, path: STATIONS_PATH }
  } catch (error) {
    const message = error instanceof ApiError ? error.message : String(error)
    const status = error instanceof ApiError && error.status >= 400 ? error.status : 502
    throw new ApiError(`無法從後端 (${BACKEND_URL}) 取得充電站列表：${message}`, status)
  }
}

export async function fetchBackendRecommendationsRaw(
  payload: RecommendPayload,
  clientIp?: string | null
): Promise<{ data: unknown; path: string }> {
  try {
    const data = await fetchJson(
      `${BACKEND_URL}${RECOMMEND_PATH}`,
      {
        method: "POST",
        headers: backendHeaders(clientIp),
        body: JSON.stringify({
          lat: payload.lat,
          lng: payload.lng,
          battery_pct: payload.batteryPercent,
          available_now: Boolean(payload.isAvailableNow),
          limit: RECOMMEND_LIMIT,
          lang: "zh",
        }),
      },
      // One OSRM table call plus scoring; normally well under a few seconds.
      20000
    )
    return { data, path: RECOMMEND_PATH }
  } catch (error) {
    const message = error instanceof ApiError ? error.message : String(error)
    const status = error instanceof ApiError && error.status >= 400 ? error.status : 502
    throw new ApiError(`無法從後端 (${BACKEND_URL}) 取得推薦：${message}`, status)
  }
}
