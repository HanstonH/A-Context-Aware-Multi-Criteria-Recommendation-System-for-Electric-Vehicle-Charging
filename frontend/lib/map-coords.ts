import type { MapBounds } from "@/lib/locations"
import { TAIWAN_BOUNDS } from "@/lib/map-constants"

export interface GeoPoint {
  lat: number
  lng: number
}

let activeBounds: MapBounds = TAIWAN_BOUNDS

/** 由充電樁資料設定地圖可視範圍（在資料載入後呼叫） */
export function setMapBounds(bounds: MapBounds) {
  activeBounds = bounds
}

export function getMapBounds(): MapBounds {
  return activeBounds
}

export function getDefaultCurrentLocation(): GeoPoint | null {
  return null
}

export function latLngToPercent(point: GeoPoint, bounds: MapBounds = activeBounds): { top: number; left: number } {
  const { north, south, east, west } = bounds
  const left = ((point.lng - west) / (east - west)) * 100
  const top = ((north - point.lat) / (north - south)) * 100
  return {
    top: Math.min(96, Math.max(4, top)),
    left: Math.min(96, Math.max(4, left)),
  }
}

export function percentToLatLng(top: number, left: number, bounds: MapBounds = activeBounds): GeoPoint {
  const { north, south, east, west } = bounds
  const lat = north - (top / 100) * (north - south)
  const lng = west + (left / 100) * (east - west)
  return { lat, lng }
}

export function clickToLatLng(
  clientX: number,
  clientY: number,
  rect: DOMRect,
  bounds: MapBounds = activeBounds
): GeoPoint {
  const left = ((clientX - rect.left) / rect.width) * 100
  const top = ((clientY - rect.top) / rect.height) * 100
  return percentToLatLng(top, left, bounds)
}

export function formatLatLng(point: GeoPoint): string {
  const latH = point.lat >= 0 ? "N" : "S"
  const lngH = point.lng >= 0 ? "E" : "W"
  return `${Math.abs(point.lat).toFixed(5)}°${latH}, ${Math.abs(point.lng).toFixed(5)}°${lngH}`
}

export function haversineKm(a: GeoPoint, b: GeoPoint): number {
  const earthKm = 6371
  const dLat = ((b.lat - a.lat) * Math.PI) / 180
  const dLng = ((b.lng - a.lng) * Math.PI) / 180
  const lat1 = (a.lat * Math.PI) / 180
  const lat2 = (b.lat * Math.PI) / 180
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2
  return 2 * earthKm * Math.asin(Math.min(1, Math.sqrt(h)))
}
