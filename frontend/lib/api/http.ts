export class ApiError extends Error {
  status: number
  body: string

  constructor(message: string, status = 500, body = "") {
    super(message)
    this.name = "ApiError"
    this.status = status
    this.body = body
  }
}

export async function fetchJson(
  url: string,
  init: RequestInit = {},
  timeoutMs = 10000
): Promise<unknown> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)

  try {
    const res = await fetch(url, {
      ...init,
      signal: controller.signal,
      headers: {
        Accept: "application/json",
        ...(init.body ? { "Content-Type": "application/json" } : {}),
        ...init.headers,
      },
    })

    const text = await res.text()
    const data = text ? parseJsonSafe(text) : null

    if (!res.ok) {
      const detail = extractErrorMessage(data) || text.slice(0, 240) || res.statusText
      throw new ApiError(`HTTP ${res.status}：${detail}`, res.status, text)
    }

    return data
  } catch (error) {
    if (error instanceof ApiError) throw error
    if (error instanceof Error && error.name === "AbortError") {
      throw new ApiError(`連線逾時：${url}`, 408)
    }
    const message = error instanceof Error ? error.message : "未知錯誤"
    throw new ApiError(`無法連線：${message}`, 0)
  } finally {
    clearTimeout(timer)
  }
}

function parseJsonSafe(text: string): unknown {
  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}

export function extractErrorMessage(data: unknown): string | null {
  if (data == null) return null
  if (typeof data === "string" && data.trim()) return data.trim()
  if (typeof data !== "object") return null
  const rec = data as Record<string, unknown>
  const detail = rec.detail ?? rec.error ?? rec.message ?? rec.msg
  if (typeof detail === "string" && detail.trim()) return detail.trim()
  if (Array.isArray(detail) && detail[0] && typeof detail[0] === "object") {
    const first = detail[0] as Record<string, unknown>
    if (typeof first.msg === "string") return first.msg
  }
  return null
}

export function extractArray(data: unknown): unknown[] {
  if (Array.isArray(data)) return data
  if (!data || typeof data !== "object") return []
  const rec = data as Record<string, unknown>
  const keys = [
    "stations",
    "locations",
    "chargers",
    "recommendations",
    "results",
    "items",
    "data",
    "rows",
    "best_stations",
    "recommended",
    "records",
  ]
  for (const key of keys) {
    if (Array.isArray(rec[key])) return rec[key] as unknown[]
  }
  const nested = rec.data
  if (nested && typeof nested === "object" && !Array.isArray(nested)) {
    return extractArray(nested)
  }
  return []
}
