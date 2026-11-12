import type { GeoPoint } from "@/lib/map-coords"
import { latLngToPercent } from "@/lib/map-coords"
import { getMapEvChargers, type ChargerPowerType, type Location } from "@/lib/locations"
import type { MapBounds } from "@/lib/locations"
import type { ConnectorAvailability, StationStatus } from "@/lib/charger-availability"

export type { ChargerPowerType }

export interface ChargingStation {
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
  chargerType: ChargerPowerType
  typeLabel: string
  price: number
  available: number
  totalChargers: number
  availableChargers: number
  stationStatus: StationStatus
  portAvailability: ConnectorAvailability[]
  lat: number
  lng: number
  isRecommended?: boolean
  recommendRank?: number
  recommendScore?: number
  recommendReason?: string
  recommendDistanceKm?: number
}

function toChargingStation(loc: Location): ChargingStation | null {
  const latitude = Number(loc?.latitude ?? loc?.lat)
  const longitude = Number(loc?.longitude ?? loc?.lng)
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return null

  const available = loc?.availableChargers ?? loc?.availableSlots ?? loc?.spaces ?? 0
  const total = loc?.totalChargers ?? loc?.charging_points ?? available
  const station_name = loc?.station_name ?? loc?.name ?? "未命名充電站"
  const typeLabel =
    loc?.charging_rate ||
    (loc?.chargerType === "DC" ? "DC 快充" : "AC 慢充")

  return {
    id: loc?.id ?? `${station_name}-${latitude}-${longitude}`,
    station_name,
    city: loc?.city,
    latitude,
    longitude,
    spaces: loc?.spaces,
    charging_points: loc?.charging_points,
    address: loc?.address ?? "—",
    service_time: loc?.service_time,
    charging_rate: loc?.charging_rate,
    parking_rate: loc?.parking_rate,
    name: station_name,
    chargerType: loc?.chargerType ?? "AC",
    typeLabel,
    price: loc?.price ?? 0,
    available,
    totalChargers: total,
    availableChargers: available,
    stationStatus: loc?.stationStatus ?? "online",
    portAvailability: loc?.portAvailability ?? [],
    lat: latitude,
    lng: longitude,
    isRecommended: loc?.isRecommended,
    recommendRank: loc?.recommendRank,
    recommendScore: loc?.recommendScore,
    recommendReason: loc?.recommendReason,
    recommendDistanceKm: loc?.recommendDistanceKm,
  }
}

/** 將 Location 陣列轉為地圖用 ChargingStation */
export function locationsToChargingStations(locations: Location[]): ChargingStation[] {
  return getMapEvChargers(locations)
    .map(toChargingStation)
    .filter((station): station is ChargingStation => station != null)
}

export function getStationPosition(station: ChargingStation, bounds?: MapBounds) {
  return latLngToPercent({ lat: station.lat, lng: station.lng }, bounds)
}

export function filterStationsForRange(
  stations: ChargingStation[],
  lowBatteryMode: boolean,
  recommendedActive = false
): ChargingStation[] {
  if (recommendedActive) return stations
  if (!lowBatteryMode) return stations
  return stations.filter((s) => s.chargerType === "DC")
}

export const LOW_BATTERY_THRESHOLD = 20
