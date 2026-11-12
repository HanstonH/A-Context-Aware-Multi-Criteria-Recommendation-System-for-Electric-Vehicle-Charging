import { NextResponse, type NextRequest } from "next/server"
import { authErrorMessage, callBackend, setSessionCookie } from "@/lib/api/auth-server"

export async function POST(request: NextRequest) {
  const body = (await request.json().catch(() => ({}))) as Record<string, unknown>
  const { status, data } = await callBackend("/api/auth/login", {
    method: "POST",
    body: { email: body.email, password: body.password },
    request,
  })
  if (status !== 200 || typeof data.token !== "string") {
    return NextResponse.json({ error: authErrorMessage(status, data.error) }, { status: status || 502 })
  }
  const response = NextResponse.json({ user: data.user })
  setSessionCookie(response, data.token)
  return response
}
