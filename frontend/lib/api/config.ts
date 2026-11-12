/** 瀏覽器一律打 Next.js 同源 API，由伺服器端再轉發後端，避免 CORS。 */
export const CLIENT_STATIONS_URL = "/api/stations"
export const CLIENT_RECOMMEND_URL = "/api/recommend"

/** Flask 後端（backend/），與手機 App 共用。本機預設埠 8000。 */
const DEFAULT_BACKEND_URL = "http://localhost:8000"

function envUrl(...keys: string[]): string | undefined {
  for (const key of keys) {
    const raw = process.env[key]
    if (!raw) continue
    const cleaned = raw.trim().replace(/\/$/, "")
    if (cleaned) return cleaned
  }
  return undefined
}

/** 共用後端網址。優先讀 BACKEND_URL，其次相容舊名 EXPRESS_BACKEND_URL / EXPRESS_API_URL。 */
export const BACKEND_URL =
  envUrl("BACKEND_URL", "EXPRESS_BACKEND_URL", "EXPRESS_API_URL") || DEFAULT_BACKEND_URL

/** 後端若設定了 APP_API_KEY，這裡填同一個值（只在伺服器端使用，不會送到瀏覽器）。 */
export const BACKEND_API_KEY = (process.env.BACKEND_API_KEY ?? "").trim()
