import { mapSupabaseRowToLocation, type Location, type SupabaseStationRow } from "@/lib/locations"
import { parseNumeric } from "@/lib/charger-availability"
import { extractArray } from "@/lib/api/http"

export interface RecommendItem {
  id: string | number
  name?: string
  rank: number
  score?: number
  reason?: string
  distanceKm?: number
  lat?: number
  lng?: number
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null
  return value as Record<string, unknown>
}

function pick(rec: Record<string, unknown>, keys: string[]): unknown {
  for (const key of keys) {
    if (rec[key] != null && rec[key] !== "") return rec[key]
  }
  return undefined
}

function pickNumber(rec: Record<string, unknown>, keys: string[]): number | undefined {
  return parseNumeric(pick(rec, keys))
}

function pickString(rec: Record<string, unknown>, keys: string[]): string | undefined {
  const value = pick(rec, keys)
  if (typeof value === "string" && value.trim()) return value.trim()
  if (typeof value === "number" && Number.isFinite(value)) return String(value)
  return undefined
}

function coordsFromRecord(rec: Record<string, unknown>): { lat?: number; lng?: number } {
  const nested =
    asRecord(rec.location) ||
    asRecord(rec.coords) ||
    asRecord(rec.coordinate) ||
    asRecord(rec.position) ||
    asRecord(rec.geo)

  const geo = asRecord(rec.geometry)
  const geoCoords = Array.isArray(geo?.coordinates) ? (geo.coordinates as unknown[]) : null

  const lat =
    pickNumber(rec, ["Latitude", "latitude", "lat", "user_lat", "station_lat"]) ??
    (nested ? pickNumber(nested, ["Latitude", "latitude", "lat"]) : undefined) ??
    (geoCoords && typeof geoCoords[1] === "number" ? geoCoords[1] : undefined)

  const lng =
    pickNumber(rec, ["Longitude", "longitude", "lng", "lon", "long", "user_lng", "station_lng"]) ??
    (nested ? pickNumber(nested, ["Longitude", "longitude", "lng", "lon", "long"]) : undefined) ??
    (geoCoords && typeof geoCoords[0] === "number" ? geoCoords[0] : undefined)

  return { lat, lng }
}

/** 將 Express / 任意 JSON 站點轉成前端 Location */
export function mapApiStationToLocation(raw: unknown): Location | null {
  const rec = asRecord(raw)
  if (!rec) return null

  const { lat, lng } = coordsFromRecord(rec)
  const name = pickString(rec, [
    "Station Name",
    "station_name",
    "name",
    "title",
    "station",
    "label",
  ])
  if (!name || lat == null || lng == null) return null

  const row: SupabaseStationRow = {
    id: pickString(rec, ["id", "station_id", "_id", "uuid"]) ?? `${name}-${lat}-${lng}`,
    station_name: name,
    latitude: lat,
    longitude: lng,
    address: pickString(rec, ["address", "Address 1", "addr", "street"]),
    city: pickString(rec, ["city", "City"]),
    spaces: pickNumber(rec, ["spaces"]),
    charging_points: pickNumber(rec, ["charging_points"]),
    service_time: pickString(rec, ["service_time"]),
    charging_rate: pickString(rec, ["charging_rate"]),
    parking_rate: pickString(rec, ["parking_rate"]),
  }

  return mapSupabaseRowToLocation(row)
}

export function mapApiStationsToLocations(data: unknown): Location[] {
  const rows = extractArray(data)
  const locations: Location[] = []
  for (const row of rows) {
    const mapped = mapApiStationToLocation(row)
    if (mapped) locations.push(mapped)
  }
  return locations
}

export function mapRecommendResponse(data: unknown): RecommendItem[] {
  const rec = asRecord(data)
  const rows = extractArray(data)
  const list =
    rows.length > 0
      ? rows
      : rec && (rec.station_id != null || rec.id != null || rec.name != null)
        ? [rec]
        : []

  return list
    .map((item, index) => mapRecommendItem(item, index))
    .filter((item): item is RecommendItem => item != null)
}

function mapRecommendItem(raw: unknown, index: number): RecommendItem | null {
  const rec = asRecord(raw)
  if (!rec) return null

  const nestedStation = asRecord(rec.station) || asRecord(rec.location)
  const merged = { ...(nestedStation ?? {}), ...rec }
  const { lat, lng } = coordsFromRecord(merged)
  const resolvedLng = lng ?? pickNumber(merged, ["lon"])
  const id =
    pickString(merged, ["id", "station_id", "stationId", "StationID", "_id", "uuid"]) ??
    pickString(merged, ["Station Name", "name", "station_name", "title"])
  if (!id && lat == null && resolvedLng == null) return null

  const distanceKmExplicit = pickNumber(merged, ["distance_km", "distanceKm"])
  const distanceRaw = pickNumber(merged, ["distance", "straight_line_m", "km"])
  const distanceKm =
    distanceKmExplicit ??
    (distanceRaw != null ? (distanceRaw > 250 ? distanceRaw / 1000 : distanceRaw) : undefined)

  return {
    id: id ?? `${lat}-${resolvedLng}`,
    name: pickString(merged, ["Station Name", "name", "station_name", "title", "station"]),
    rank: pickNumber(merged, ["rank", "order", "priority"]) ?? index + 1,
    score: pickNumber(merged, ["topsis_score", "total_score", "score", "rating", "confidence", "probability"]),
    reason: pickString(merged, ["reason", "explanation", "why", "message", "note"]),
    distanceKm,
    lat,
    lng: resolvedLng,
  }
}

export function applyRecommendations(
  locations: Location[],
  items: RecommendItem[]
): Location[] {
  const byId = new Map<string, RecommendItem>()
  const byName = new Map<string, RecommendItem>()
  for (const item of items) {
    byId.set(String(item.id).toLowerCase(), item)
    if (item.name) byName.set(item.name.trim().toLowerCase(), item)
  }

  const applied = locations.map((loc) => {
    const rec =
      byId.get(String(loc.id).toLowerCase()) ??
      byName.get(loc.name.trim().toLowerCase())
    if (!rec) {
      return {
        ...loc,
        isRecommended: false,
        recommendRank: undefined,
        recommendScore: undefined,
        recommendReason: undefined,
        recommendDistanceKm: undefined,
      }
    }
    return {
      ...loc,
      isRecommended: true,
      recommendRank: rec.rank,
      recommendScore: rec.score,
      recommendReason: rec.reason,
      recommendDistanceKm: rec.distanceKm,
    }
  })

  const matchedIds = new Set(
    applied.filter((loc) => loc.isRecommended).map((loc) => String(loc.id).toLowerCase())
  )
  const extras: Location[] = []
  for (const item of items) {
    if (matchedIds.has(String(item.id).toLowerCase())) continue
    if (item.name && applied.some((loc) => loc.isRecommended && loc.name === item.name)) continue
    if (item.lat == null || item.lng == null) continue
    extras.push({
      id: String(item.id),
      station_name: item.name ?? `AI 推薦站 #${item.rank}`,
      name: item.name ?? `AI 推薦站 #${item.rank}`,
      address: item.reason ?? "FastAPI 推薦充電站",
      type: "ev-charger",
      latitude: item.lat,
      longitude: item.lng,
      lat: item.lat,
      lng: item.lng,
      isRecommended: true,
      recommendRank: item.rank,
      recommendScore: item.score,
      recommendReason: item.reason,
      recommendDistanceKm: item.distanceKm,
    })
  }

  return [...extras, ...applied]
}
