import { haversineKm } from "@/lib/map-coords"
import type { GeoPoint } from "@/lib/map-coords"
import type { Location } from "@/lib/locations"
import { topsisRank } from "@/lib/ai/topsis"
import { contextStateLabel } from "@/lib/ai/weights"
import type { RecommendItem } from "@/lib/api/normalize"

export interface StationRankInput {
  id: string
  name: string
  lat: number
  lng: number
  cost?: number
  available?: number
  total?: number
  poiCount?: number
}

const FULL_RANGE_KM = 300
const RANGE_SAFETY = 0.8
const MAX_CANDIDATES = 10

export function nearestStationInputs(
  stations: StationRankInput[],
  origin: GeoPoint,
  limit = 80
): StationRankInput[] {
  return [...stations]
    .sort(
      (a, b) =>
        haversineKm(origin, { lat: a.lat, lng: a.lng }) -
        haversineKm(origin, { lat: b.lat, lng: b.lng })
    )
    .slice(0, limit)
}

export function locationsToRankInput(locations: Location[]): StationRankInput[] {
  const rows: StationRankInput[] = []
  for (const loc of locations) {
    const lat = Number(loc.latitude ?? loc.lat)
    const lng = Number(loc.longitude ?? loc.lng)
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) continue
    rows.push({
      id: String(loc.id),
      name: loc.station_name ?? loc.name,
      lat,
      lng,
      cost: loc.price ?? 0,
      available: loc.availableChargers ?? loc.availableSlots ?? loc.spaces ?? 0,
      total: loc.totalChargers ?? loc.charging_points ?? 0,
      poiCount: 0,
    })
  }
  return rows
}

export function rankStationsWithTopsis(
  stations: StationRankInput[],
  origin: GeoPoint,
  batteryPercent: number,
  isAvailableNow = false,
  maxCandidates = MAX_CANDIDATES
): RecommendItem[] {
  const reachableMetres =
    Math.min(1, Math.max(0, batteryPercent / 100)) * FULL_RANGE_KM * 1000 * RANGE_SAFETY

  const withDistance = stations.map((station) => {
    const distanceM = haversineKm(origin, { lat: station.lat, lng: station.lng }) * 1000
    return { ...station, distance: distanceM }
  })

  let candidates = withDistance.filter((row) => row.distance <= reachableMetres)
  if (candidates.length === 0) {
    candidates = [...withDistance].sort((a, b) => a.distance - b.distance).slice(0, maxCandidates)
  } else {
    const available = candidates.filter((row) => (row.available ?? 0) >= 1)
    candidates = (available.length > 0 ? available : candidates)
      .sort((a, b) => a.distance - b.distance)
      .slice(0, maxCandidates)
  }

  const ranked = topsisRank(
    candidates.map((row) => ({
      id: row.id,
      distance: row.distance,
      poiCount: row.poiCount ?? 0,
      cost: row.cost ?? 0,
      availablePots: row.available ?? 0,
      name: row.name,
      lat: row.lat,
      lng: row.lng,
    })),
    batteryPercent / 100,
    isAvailableNow
  )

  const state = contextStateLabel(batteryPercent / 100, isAvailableNow)
  return ranked.map((row, index) => ({
    id: row.id,
    name: row.name,
    rank: index + 1,
    score: row.topsisScore,
    reason: `${state} · TOPSIS ${row.topsisScore.toFixed(3)} · ${(row.distance / 1000).toFixed(1)} km`,
    distanceKm: row.distance / 1000,
    lat: row.lat,
    lng: row.lng,
  }))
}
