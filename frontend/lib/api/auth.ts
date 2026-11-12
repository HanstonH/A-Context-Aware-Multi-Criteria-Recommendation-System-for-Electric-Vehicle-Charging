/** Browser-side login calls. They hit the Next.js /api/auth/* routes (same origin). */

export interface AuthUser {
  id: number
  email: string
  name: string | null
}

async function post(path: string, body?: unknown): Promise<AuthUser> {
  let res: Response
  try {
    res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new Error("無法連線到伺服器，請稍後再試")
  }
  const data = (await res.json().catch(() => ({}))) as { user?: AuthUser; error?: string }
  if (!res.ok || !data.user) throw new Error(data.error || "發生錯誤，請稍後再試")
  return data.user
}

export function login(email: string, password: string): Promise<AuthUser> {
  return post("/api/auth/login", { email, password })
}

export function register(email: string, password: string, name: string): Promise<AuthUser> {
  return post("/api/auth/register", { email, password, name: name || undefined })
}

/** The logged-in user from the session cookie, or null. */
export async function fetchCurrentUser(): Promise<AuthUser | null> {
  try {
    const res = await fetch("/api/auth/me", { cache: "no-store" })
    if (!res.ok) return null
    const data = (await res.json()) as { user?: AuthUser | null }
    return data.user ?? null
  } catch {
    return null
  }
}

export async function logout(): Promise<void> {
  await fetch("/api/auth/logout", { method: "POST" }).catch(() => undefined)
}

/** Up to two letters for the avatar: from the name, else the email. */
export function userInitials(user: AuthUser): string {
  const source = (user.name || user.email.split("@")[0]).trim()
  const words = source.split(/\s+/).filter(Boolean)
  const letters = words.length > 1 ? words[0][0] + words[1][0] : source.slice(0, 2)
  return letters.toUpperCase()
}
