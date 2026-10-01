import type { LucideIcon } from "lucide-react"
import { Home, Building2, Utensils, Zap } from "lucide-react"
import { getSupabaseClient } from "@/lib/supabase/client"
import { TAIWAN_BOUNDS, NEARBY_SEARCH_RADIUS_KM } from "@/lib/map-constants"
import { haversineKm, type GeoPoint } from "@/lib/map-coords"
import {
  inferAvailableChargers,
  inferTotalChargers,
  parsePortAvailability,
  simulatePortAvailability,
  type ConnectorAvailability,
  type StationStatus,
} from "@/lib/charger-availability"

export type ChargerPowerType = "DC" | "AC"

export type LocationType = "home" | "office" | "restaurant" | "ev-charger" | "landmark"

export interface Location {
  id: number | string
  station_name?: string
  city?: string
  latitude?: number
  longitude?: number
  spaces?: number
  charging_points?: number
  address?: string
  service_time?: string
  charging_rate?: string
  parking_rate?: string
  name: string
  type: LocationType
  price?: number
  chargerType?: ChargerPowerType
  availableSlots?: number
  totalChargers?: number
  availableChargers?: number
  stationStatus?: StationStatus
  lat?: number
  lng?: number
  portType?: string
  plugType?: string
  portAvailability?: ConnectorAvailability[]
  isRecommended?: boolean
  recommendRank?: number
  recommendScore?: number
  recommendReason?: string
  recommendDistanceKm?: number
}

/** Supabase `public.stations` 實際欄位（全小寫 snake_case） */
export interface SupabaseStationRow {
  id?: string | number | null
  station_name?: string | null
  city?: string | null
  latitude?: number | string | null
  longitude?: number | string | null
  spaces?: number | string | null
  charging_points?: number | string | null
  address?: string | null
  service_time?: string | null
  charging_rate?: string | null
  parking_rate?: string | null
  [key: string]: unknown
}

/** @deprecated 請改用 SupabaseStationRow */
export type SupabaseLocationRow = SupabaseStationRow

export interface MapBounds {
  north: number
  south: number
  east: number
  west: number
}

const DEFAULT_MAP_BOUNDS: MapBounds = TAIWAN_BOUNDS

/** 本地示範用地標（非 Supabase） */
export const staticDemoLocations: Location[] = [
  {
    id: 1,
    name: "台北101",
    address: "台北市信義區信義路五段 7 號",
    type: "landmark",
  },
  {
    id: 2,
    name: "誠品生活松菸店",
    address: "台北市信義區菸廠路 88 號",
    type: "landmark",
  },
  {
    id: 3,
    name: "大安森林公園",
    address: "台北市大安區新生南路二段 1 號",
    type: "landmark",
  },
]

export const favoriteLocations: (Location & { icon: LucideIcon })[] = [
  {
    id: 101,
    name: "住家",
    address: "新北市中和區景安路101巷12號5樓",
    type: "home",
    icon: Home,
  },
  {
    id: 102,
    name: "公司",
    address: "台北市中山區南京東路三段 219 號",
    type: "office",
    icon: Building2,
  },
]

export const quickActions: {
  icon: LucideIcon
  label: string
  filterType: LocationType
}[] = [
  { icon: Home, label: "住家", filterType: "home" },
  { icon: Building2, label: "公司", filterType: "office" },
  { icon: Utensils, label: "餐廳", filterType: "restaurant" },
  { icon: Zap, label: "充電樁", filterType: "ev-charger" },
]

function col(row: Record<string, unknown>, ...keys: string[]): unknown {
  for (const key of keys) {
    if (row[key] != null && row[key] !== "") return row[key]
  }
  return undefined
}

function firstNumber(...values: unknown[]): number | undefined {
  for (const value of values) {
    const n = Number(value)
    if (Number.isFinite(n)) return n
  }
  return undefined
}

function firstString(
  ...values: Array<string | number | null | undefined | unknown>
): string | undefined {
  for (const value of values) {
    if (typeof value === "string" && value.trim()) return value.trim()
    if (typeof value === "number" && Number.isFinite(value)) return String(value)
  }
  return undefined
}

function parseChargerType(chargingRate?: string | null): ChargerPowerType {
  const combined = `${chargingRate ?? ""}`.toLowerCase()
  if (combined.includes("dc") || combined.includes("fast") || combined.includes("快充")) return "DC"
  return "AC"
}

/** 將 Supabase `stations` 列轉為前端 Location */
export function mapSupabaseRowToLocation(row: SupabaseStationRow): Location | null {
  const rec = row as Record<string, unknown>
  const station_name = firstString(
    col(rec, "station_name", "Station Name", "name")
  )
  const latitude = firstNumber(col(rec, "latitude", "Latitude", "lat"))
  const longitude = firstNumber(col(rec, "longitude", "Longitude", "lng", "lon"))

  if (latitude == null || longitude == null) return null

  const name = station_name || "未命名充電站"
  const id = firstString(col(rec, "id")) ?? `${name}-${latitude}-${longitude}`
  const charging_points = firstNumber(col(rec, "charging_points"))
  const spaces = firstNumber(col(rec, "spaces"))
  const charging_rate = firstString(col(rec, "charging_rate"))
  const address = firstString(col(rec, "address", "Address 1")) ?? "—"
  const city = firstString(col(rec, "city", "City"))
  const totalChargers = charging_points ?? inferTotalChargers(id, spaces ?? 0)
  const availableFromDb =
    spaces != null ? Math.max(0, Math.min(spaces, totalChargers)) : undefined
  const availableChargers = availableFromDb ?? inferAvailableChargers(id, totalChargers)
  const clampedAvailable = Math.max(0, Math.min(availableChargers, totalChargers))

  return {
    id,
    station_name: name,
    city,
    latitude,
    longitude,
    spaces,
    charging_points,
    address,
    service_time: firstString(col(rec, "service_time")),
    charging_rate,
    parking_rate: firstString(col(rec, "parking_rate")),
    name,
    type: "ev-charger",
    chargerType: parseChargerType(charging_rate),
    availableSlots: clampedAvailable,
    totalChargers,
    availableChargers: clampedAvailable,
    stationStatus: "online",
    lat: latitude,
    lng: longitude,
    portAvailability: parsePortAvailability(
      undefined,
      totalChargers,
      clampedAvailable,
      charging_rate,
      id
    ),
  }
}

export function formatStationSchemaDetails(loc?: {
  city?: string | null
  address?: string | null
  service_time?: string | null
  charging_rate?: string | null
  parking_rate?: string | null
  spaces?: number | null
  charging_points?: number | null
} | null): string[] {
  const lines: string[] = []
  if (loc?.city) lines.push(loc.city)
  if (loc?.service_time) lines.push(`服務時間：${loc.service_time}`)
  if (loc?.charging_rate) lines.push(`充電費率：${loc.charging_rate}`)
  if (loc?.parking_rate) lines.push(`停車費率：${loc.parking_rate}`)
  if (loc?.spaces != null) lines.push(`車位：${loc.spaces}`)
  if (loc?.charging_points != null) lines.push(`充電樁：${loc.charging_points}`)
  return lines
}

export function stationSchemaCardProps(
  loc?: Pick<
    Location,
    "city" | "service_time" | "charging_rate" | "parking_rate" | "spaces" | "charging_points"
  > | null
) {
  return {
    city: loc?.city,
    service_time: loc?.service_time,
    charging_rate: loc?.charging_rate,
    parking_rate: loc?.parking_rate,
    spaces: loc?.spaces,
    charging_points: loc?.charging_points,
  }
}

/**
 * 從 Supabase `stations` 讀取充電樁（欄位名與資料庫完全一致，含空格與大小寫）。
 */
export async function fetchLocationsFromSupabase(): Promise<Location[]> {
  const client = getSupabaseClient()
  const { data, error } = await client
    .from("stations")
    .select("*")
    .range(0, 4000)

  console.log("抓到的站點總數：", data?.length, "錯誤訊息：", error)

  if (error) {
    console.error("[Supabase] fetch stations failed:", error.message)
    throw new Error(`無法讀取充電樁資料：${error.message}`)
  }

  const chargers: Location[] = []
  for (const row of (data ?? []) as SupabaseStationRow[]) {
    const mapped = mapSupabaseRowToLocation(row)
    if (mapped) chargers.push(mapped)
  }
  console.log("對應後可顯示站點數：", chargers.length)
  return chargers
}

/** 本地模擬空槍數量變動（不寫回資料庫，方便測試燈號） */
export function simulateLocationAvailability(locations: Location[]): Location[] {
  const eligibleIndexes = locations
    .map((loc, index) => ({ loc, index }))
    .filter(
      ({ loc }) =>
        loc.type === "ev-charger" &&
        loc.stationStatus !== "offline" &&
        loc.stationStatus !== "maintenance" &&
        (loc.totalChargers ?? 0) > 0
    )
    .map(({ index }) => index)

  const forcedAvailable = new Map<number, number>()
  const shuffled = [...eligibleIndexes].sort(() => Math.random() - 0.5)
  const forceTargets: Array<(total: number) => number> = [
    () => 0,
    (total) => Math.min(1, total),
    (total) => Math.min(2, total),
    (total) => total,
  ]
  shuffled.slice(0, forceTargets.length).forEach((index, i) => {
    const fn = forceTargets[i]
    const total = locations[index]?.totalChargers ?? 0
    if (fn) forcedAvailable.set(index, fn(total))
  })

  return locations.map((loc, index) => {
    if (loc.type !== "ev-charger") return loc
    if (loc.stationStatus === "offline" || loc.stationStatus === "maintenance") return loc

    const total = loc.totalChargers ?? 0
    if (total <= 0) return loc

    const ports = loc.portAvailability?.length
      ? simulatePortAvailability(loc.portAvailability)
      : []
    let available = ports.length
      ? ports.reduce((sum, p) => sum + p.available, 0)
      : Math.floor(Math.random() * (total + 1))

    if (forcedAvailable.has(index)) {
      available = forcedAvailable.get(index)!
      if (ports.length) {
        let remaining = available
        for (let i = 0; i < ports.length; i++) {
          const isLast = i === ports.length - 1
          const slot = isLast ? remaining : Math.min(ports[i].total, remaining)
          ports[i] = { ...ports[i], available: Math.max(0, Math.min(ports[i].total, slot)) }
          remaining -= slot
        }
      }
    }

    return {
      ...loc,
      availableChargers: available,
      availableSlots: available,
      portAvailability: ports.length ? ports : loc.portAvailability,
    }
  })
}

/** 合併靜態示範地標 + Supabase 充電樁 */
export function mergeAllLocations(evChargers: Location[]): Location[] {
  return [...staticDemoLocations, ...evChargers]
}

/** 具備經緯度的 ev-charger（地圖標記用） */
export function getMapEvChargers(locations: Location[]): Location[] {
  return locations.filter((loc) => {
    if (loc?.type !== "ev-charger") return false
    const lat = Number(loc?.latitude ?? loc?.lat)
    const lng = Number(loc?.longitude ?? loc?.lng)
    return Number.isFinite(lat) && Number.isFinite(lng)
  })
}

/** 以中心點篩出周遭充電站 */
export function filterLocationsNear(
  items: Location[],
  center: GeoPoint,
  radiusKm: number = NEARBY_SEARCH_RADIUS_KM
): Location[] {
  return items.filter((item) => {
    if (item?.type !== "ev-charger") return false
    const lat = Number(item?.latitude ?? item?.lat)
    const lng = Number(item?.longitude ?? item?.lng)
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) return false
    return haversineKm(center, { lat, lng }) <= radiusKm
  })
}

/** 依充電樁座標計算地圖邊界 */
export function computeMapBoundsFromChargers(chargers: Location[]): MapBounds {
  const withCoords = getMapEvChargers(chargers)
  if (withCoords.length === 0) return DEFAULT_MAP_BOUNDS

  const lats = withCoords.map((c) => Number(c?.latitude ?? c?.lat))
  const lngs = withCoords.map((c) => Number(c?.longitude ?? c?.lng))
  const pad = 0.05

  return {
    north: Math.max(...lats) + pad,
    south: Math.min(...lats) - pad,
    east: Math.max(...lngs) + pad,
    west: Math.min(...lngs) - pad,
  }
}

export function formatChargerPrice(price: number): string {
  if (price === 0) return "Free（免費）"
  return `Fee $${price.toFixed(2)}`
}

export function filterLocations(
  items: Location[],
  typeFilter: LocationType | null,
  searchQuery?: string
): Location[] {
  return items.filter((item) => {
    if (typeFilter && item.type !== typeFilter) return false
    if (searchQuery && !item.name.toLowerCase().includes(searchQuery.toLowerCase())) {
      return false
    }
    return true
  })
}

export function findLocationByName(
  name: string,
  allLocations: Location[]
): Location | undefined {
  return [...allLocations, ...favoriteLocations].find((loc) => loc.name === name)
}
