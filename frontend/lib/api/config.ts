/** 瀏覽器一律打 Next.js 同源 API，由伺服器端再轉發後端，避免 CORS。 */
export const CLIENT_STATIONS_URL = "/api/stations"
export const CLIENT_RECOMMEND_URL = "/api/recommend"

const DEFAULT_EXPRESS_URL = "http://localhost:5000"
const DEFAULT_FASTAPI_URL = "http://127.0.0.1:8000"

function envUrl(...keys: string[]): string | undefined {
  for (const key of keys) {
    const raw = process.env[key]
    if (!raw) continue
    const cleaned = raw.trim().replace(/\/$/, "")
    if (cleaned) return cleaned
  }
  return undefined
}

/** Express 後端。優先讀 EXPRESS_BACKEND_URL，其次相容舊名 EXPRESS_API_URL。 */
export const EXPRESS_API_URL =
  envUrl("EXPRESS_BACKEND_URL", "EXPRESS_API_URL") || DEFAULT_EXPRESS_URL

export const EXPRESS_BACKEND_URL = EXPRESS_API_URL

export const FASTAPI_URL = envUrl("FASTAPI_URL") || DEFAULT_FASTAPI_URL

export const EXPRESS_STATIONS_PATHS = uniquePaths([
  process.env.EXPRESS_STATIONS_PATH,
  "/api/stations",
  "/api/chargers",
  "/api/charging-stations",
  "/stations",
  "/chargers",
])

export const FASTAPI_RECOMMEND_PATHS = uniquePaths([
  process.env.FASTAPI_RECOMMEND_PATH,
  "/recommend",
  "/api/recommend",
  "/recommendation",
  "/predict",
  "/ai/recommend",
  "/stations/recommend",
])

function uniquePaths(paths: Array<string | undefined>): string[] {
  const seen = new Set<string>()
  const result: string[] = []
  for (const raw of paths) {
    const path = raw?.trim()
    if (!path) continue
    const normalized = path.startsWith("/") ? path : `/${path}`
    if (seen.has(normalized)) continue
    seen.add(normalized)
    result.push(normalized)
  }
  return result
}
