import type { NextRequest, NextResponse } from "next/server"
import { BACKEND_API_KEY, BACKEND_URL } from "@/lib/api/config"
import { clientIpFrom } from "@/lib/api/backend-proxy"

/**
 * Server-side half of web login. The browser only ever talks to the Next.js
 * /api/auth/* routes; the backend's login token lives in an httpOnly cookie, so
 * page JavaScript (and any injected script) can't read it.
 */

export const SESSION_COOKIE = "mapexplore_session"
const SESSION_MAX_AGE_S = 30 * 24 * 60 * 60 // matches the backend's AUTH_TOKEN_DAYS default

export interface AuthUser {
  id: number
  email: string
  name: string | null
  created_at?: string
}

export interface BackendResult {
  status: number
  data: Record<string, unknown>
}

/** Call the backend without throwing on 4xx, so its status can be passed on. */
export async function callBackend(
  path: string,
  init: { method: "GET" | "POST"; body?: unknown; token?: string; request?: NextRequest }
): Promise<BackendResult> {
  const headers: Record<string, string> = { Accept: "application/json" }
  if (init.body !== undefined) headers["Content-Type"] = "application/json"
  if (BACKEND_API_KEY) headers["X-API-Key"] = BACKEND_API_KEY
  if (init.token) headers.Authorization = `Bearer ${init.token}`
  const ip = init.request ? clientIpFrom(init.request) : null
  if (ip) headers["X-Forwarded-For"] = ip // per-visitor rate limits on the backend

  try {
    const res = await fetch(`${BACKEND_URL}${path}`, {
      method: init.method,
      headers,
      body: init.body === undefined ? undefined : JSON.stringify(init.body),
      cache: "no-store",
      signal: AbortSignal.timeout(15000),
    })
    const data = (await res.json().catch(() => ({}))) as Record<string, unknown>
    return { status: res.status, data }
  } catch {
    return { status: 503, data: { error: "backend unavailable" } }
  }
}

export function setSessionCookie(response: NextResponse, token: string) {
  response.cookies.set(SESSION_COOKIE, token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: SESSION_MAX_AGE_S,
  })
}

export function clearSessionCookie(response: NextResponse) {
  response.cookies.set(SESSION_COOKIE, "", { httpOnly: true, path: "/", maxAge: 0 })
}

/** Chinese message for the login screen, by backend status. */
export function authErrorMessage(status: number, fallback: unknown): string {
  if (status === 401) return "電子郵件或密碼錯誤"
  if (status === 409) return "此電子郵件已經註冊過了"
  if (status === 429) return "嘗試次數過多，請稍後再試"
  if (status === 503 || status === 502 || status === 0) return "無法連線到伺服器，請稍後再試"
  if (status === 400) {
    const text = typeof fallback === "string" ? fallback : ""
    if (text.includes("email")) return "請輸入有效的電子郵件"
    if (text.includes("Password")) return "密碼長度需為 8 到 128 個字元"
  }
  return "發生錯誤，請稍後再試"
}
