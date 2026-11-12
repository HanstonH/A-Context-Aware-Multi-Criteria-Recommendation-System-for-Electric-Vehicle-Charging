import { NextResponse, type NextRequest } from "next/server"
import { SESSION_COOKIE, callBackend, clearSessionCookie } from "@/lib/api/auth-server"

/** Who is logged in (from the session cookie), so a page reload keeps you signed in. */
export async function GET(request: NextRequest) {
  const token = request.cookies.get(SESSION_COOKIE)?.value
  if (!token) return NextResponse.json({ user: null }, { status: 401 })

  const { status, data } = await callBackend("/api/auth/me", { method: "GET", token, request })
  if (status === 200) return NextResponse.json({ user: data.user })

  if (status === 401) {
    // Expired or invalid token: forget it.
    const response = NextResponse.json({ user: null }, { status: 401 })
    clearSessionCookie(response)
    return response
  }
  // Backend down or rate limited: keep the cookie and let the client retry later.
  return NextResponse.json({ user: null, error: "backend unavailable" }, { status: 503 })
}
