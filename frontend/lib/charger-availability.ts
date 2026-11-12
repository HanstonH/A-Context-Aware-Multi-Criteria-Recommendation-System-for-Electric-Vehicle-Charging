export type AvailabilityLight = "green" | "yellow" | "red" | "gray"

export type StationStatus = "online" | "offline" | "maintenance"

export type ConnectorType =
  | "CCS1"
  | "CCS2"
  | "J1772"
  | "CHAdeMO"
  | "Tesla"
  | "Type2"
  | "Other"

export interface ConnectorAvailability {
  type: ConnectorType
  total: number
  available: number
}

export const CONNECTOR_LABELS: Record<ConnectorType, string> = {
  CCS1: "CCS1",
  CCS2: "CCS2",
  J1772: "J1772",
  CHAdeMO: "CHAdeMO",
  Tesla: "Tesla / NACS",
  Type2: "Type 2",
  Other: "其他",
}

export const AVAILABILITY_THEME: Record<
  AvailabilityLight,
  {
    label: string
    emoji: string
    pin: string
    pointer: string
    text: string
    bar: string
    badge: string
    track: string
    dot: string
    markerBg: string
  }
> = {
  green: {
    label: "空位充足",
    emoji: "🟢",
    pin: "bg-gradient-to-br from-emerald-400 to-emerald-600 shadow-emerald-600/40",
    pointer: "border-t-emerald-600",
    text: "text-emerald-700 dark:text-emerald-300",
    bar: "bg-emerald-500",
    badge: "bg-emerald-500/15 text-emerald-800 dark:text-emerald-200",
    track: "bg-emerald-500/20",
    dot: "bg-emerald-500",
    markerBg: "#059669",
  },
  yellow: {
    label: "槍位緊張",
    emoji: "🟡",
    pin: "bg-gradient-to-br from-amber-400 to-amber-500 shadow-amber-500/40",
    pointer: "border-t-amber-500",
    text: "text-amber-700 dark:text-amber-300",
    bar: "bg-amber-500",
    badge: "bg-amber-500/15 text-amber-800 dark:text-amber-200",
    track: "bg-amber-500/20",
    dot: "bg-amber-400",
    markerBg: "#d97706",
  },
  red: {
    label: "滿位／佔用中",
    emoji: "🔴",
    pin: "bg-gradient-to-br from-red-400 to-red-600 shadow-red-600/40",
    pointer: "border-t-red-600",
    text: "text-red-700 dark:text-red-300",
    bar: "bg-red-500",
    badge: "bg-red-500/15 text-red-800 dark:text-red-200",
    track: "bg-red-500/20",
    dot: "bg-red-500",
    markerBg: "#dc2626",
  },
  gray: {
    label: "維修中／離線",
    emoji: "⚪",
    pin: "bg-gradient-to-br from-slate-400 to-slate-500 shadow-slate-500/30",
    pointer: "border-t-slate-500",
    text: "text-slate-600 dark:text-slate-300",
    bar: "bg-slate-400",
    badge: "bg-slate-500/15 text-slate-700 dark:text-slate-300",
    track: "bg-slate-500/20",
    dot: "bg-slate-400",
    markerBg: "#64748b",
  },
}

export function normalizeStationStatus(raw?: string | null): StationStatus {
  const s = (raw ?? "").trim().toLowerCase()
  if (!s) return "online"
  if (["offline", "離線", "down", "unavailable", "unavailable/offline"].includes(s)) {
    return "offline"
  }
  if (["maintenance", "維修", "維修中", "closed", "out of service"].includes(s)) {
    return "maintenance"
  }
  return "online"
}

export function getAvailabilityLight(
  availableChargers: number,
  totalChargers: number,
  status?: StationStatus | string | null
): AvailabilityLight {
  const normalized = normalizeStationStatus(
    typeof status === "string" ? status : status ?? "online"
  )
  if (totalChargers <= 0 || normalized === "offline" || normalized === "maintenance") {
    return "gray"
  }
  if (availableChargers <= 0) return "red"
  if (availableChargers <= 2) return "yellow"
  return "green"
}

export function getAvailabilityPercent(available: number, total: number): number {
  if (total <= 0) return 0
  return Math.max(0, Math.min(100, Math.round((available / total) * 100)))
}

export function formatAvailabilityLabel(available: number, total: number): string {
  return `可充 ${available} / 總共 ${total}`
}

export function parseNumeric(value: unknown): number | undefined {
  if (value == null || value === "") return undefined
  const n = Number(value)
  return Number.isFinite(n) ? n : undefined
}

function hashId(id: string | number): number {
  const str = String(id)
  let hash = 0
  for (let i = 0; i < str.length; i++) {
    hash = (hash * 31 + str.charCodeAt(i)) >>> 0
  }
  return hash
}

/** 當資料庫尚未提供總槍數時，依站點 id 產生穩定的示範總數（4–8） */
export function inferTotalChargers(id: string | number, available: number): number {
  const total = 4 + (hashId(id) % 5)
  return Math.max(total, available, 0)
}

/** 當資料庫尚未提供空槍數時，依站點 id 產生穩定的示範空位數 */
export function inferAvailableChargers(id: string | number, total: number): number {
  if (total <= 0) return 0
  return hashId(id) % (total + 1)
}

export function detectConnectorType(portType?: string | null): ConnectorType {
  const p = (portType ?? "").toLowerCase()
  if (!p.trim()) return "Other"
  if (p.includes("ccs1") || p.includes("combo 1") || p.includes("combo1")) return "CCS1"
  if (p.includes("ccs2") || p.includes("combo 2") || p.includes("combo2")) return "CCS2"
  if (p.includes("j1772") || p.includes("j-1772") || p.includes("sae j1772")) return "J1772"
  if (p.includes("chademo")) return "CHAdeMO"
  if (p.includes("tesla") || p.includes("nacs")) return "Tesla"
  if (p.includes("type 2") || p.includes("type2") || p.includes("mennekes")) return "Type2"
  if (p.includes("ccs")) return "CCS2"
  if (p.includes("level 2") || p.includes("l2") || p.includes("ac")) return "J1772"
  if (p.includes("dc") || p.includes("fast")) return "CCS2"
  return "Other"
}

function isConnectorType(value: string): value is ConnectorType {
  return value in CONNECTOR_LABELS
}

function clampCount(value: number, max: number): number {
  return Math.max(0, Math.min(max, Math.round(value)))
}

/** 解析 Supabase `port_availability`（JSON 物件或陣列） */
export function parsePortAvailability(
  raw: unknown,
  fallbackTotal: number,
  fallbackAvailable: number,
  portType?: string | null,
  stationId?: string | number
): ConnectorAvailability[] {
  const fromJson = parsePortAvailabilityJson(raw)
  if (fromJson && fromJson.length > 0) {
    return fromJson.map((p) => ({
      ...p,
      total: Math.max(0, p.total),
      available: clampCount(p.available, p.total),
    }))
  }

  const known = detectConnectorType(portType)
  if (known !== "Other") {
    return [{ type: known, total: fallbackTotal, available: fallbackAvailable }]
  }

  return splitAcrossConnectors(stationId ?? "demo", fallbackTotal, fallbackAvailable)
}

function parsePortAvailabilityJson(raw: unknown): ConnectorAvailability[] | null {
  if (raw == null) return null

  let data = raw
  if (typeof raw === "string") {
    try {
      data = JSON.parse(raw)
    } catch {
      return null
    }
  }

  if (Array.isArray(data)) {
    const items: ConnectorAvailability[] = []
    for (const item of data) {
      if (!item || typeof item !== "object") continue
      const rec = item as Record<string, unknown>
      const typeRaw = String(rec.type ?? rec.port ?? rec.name ?? "")
      const type = isConnectorType(typeRaw) ? typeRaw : detectConnectorType(typeRaw)
      const total = parseNumeric(rec.total ?? rec.total_chargers) ?? 0
      const available = parseNumeric(rec.available ?? rec.available_chargers) ?? 0
      if (total <= 0 && available <= 0) continue
      items.push({ type, total: Math.max(total, available), available })
    }
    return items.length > 0 ? items : null
  }

  if (typeof data === "object") {
    const items: ConnectorAvailability[] = []
    for (const [key, value] of Object.entries(data as Record<string, unknown>)) {
      const type = isConnectorType(key) ? key : detectConnectorType(key)
      if (typeof value === "number") {
        items.push({ type, total: value, available: value })
        continue
      }
      if (value && typeof value === "object") {
        const rec = value as Record<string, unknown>
        const total = parseNumeric(rec.total ?? rec.total_chargers) ?? 0
        const available = parseNumeric(rec.available ?? rec.available_chargers) ?? 0
        if (total <= 0 && available <= 0) continue
        items.push({ type, total: Math.max(total, available), available })
      }
    }
    return items.length > 0 ? items : null
  }

  return null
}

function splitAcrossConnectors(
  id: string | number,
  total: number,
  available: number
): ConnectorAvailability[] {
  if (total <= 0) {
    return [
      { type: "CCS1", total: 0, available: 0 },
      { type: "CCS2", total: 0, available: 0 },
      { type: "J1772", total: 0, available: 0 },
    ]
  }

  const hash = hashId(id)
  const ccs2Share = 0.3 + ((hash % 40) / 100)
  const ccs1Share = 0.2 + (((hash >> 3) % 30) / 100)
  let ccs2 = Math.max(1, Math.round(total * ccs2Share))
  let ccs1 = Math.max(1, Math.round(total * ccs1Share))
  let j1772 = total - ccs1 - ccs2
  if (j1772 < 0) {
    ccs2 = Math.max(1, ccs2 + j1772)
    j1772 = total - ccs1 - ccs2
  }
  if (j1772 < 0) {
    ccs1 = Math.max(0, total - ccs2)
    j1772 = 0
  }

  const scaled = [
    { type: "CCS1" as const, total: ccs1 },
    { type: "CCS2" as const, total: ccs2 },
    { type: "J1772" as const, total: j1772 },
  ].filter((p) => p.total > 0)

  let remainingAvailable = available
  return scaled.map((p, i) => {
    const isLast = i === scaled.length - 1
    const slot = isLast ? remainingAvailable : Math.min(p.total, remainingAvailable)
    remainingAvailable -= slot
    return { type: p.type, total: p.total, available: clampCount(slot, p.total) }
  })
}

export function simulatePortAvailability(
  ports: ConnectorAvailability[]
): ConnectorAvailability[] {
  return ports.map((p) => ({
    ...p,
    available: p.total <= 0 ? 0 : Math.floor(Math.random() * (p.total + 1)),
  }))
}
