import type { GeoPoint } from "@/lib/map-coords"
import { haversineKm } from "@/lib/map-coords"

export type NearbyPlaceKind = "restaurant" | "cafe" | "shopping"

export interface NearbyPlace {
  id: string
  name: string
  kind: NearbyPlaceKind
  lat: number
  lng: number
  rating?: number
  openNow?: boolean | null
  vicinity?: string
  userRatingCount?: number
  distanceMeters?: number
  recommendRank?: number
  recommendScore?: number
  recommendReason?: string
  isRecommended?: boolean
}

export const NEARBY_SEARCH_RADIUS_M = 500

export const NEARBY_PLACE_META: Record<
  NearbyPlaceKind,
  { label: string; color: string; glyph: string }
> = {
  restaurant: { label: "餐廳", color: "#EF4444", glyph: "餐" },
  cafe: { label: "咖啡廳", color: "#D97706", glyph: "咖" },
  shopping: { label: "購物", color: "#3B82F6", glyph: "購" },
}

const MARKER_ICON_INNER: Record<NearbyPlaceKind, string> = {
  cafe: `<g fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M10 2v2"/><path d="M14 2v2"/><path d="M6 2v2"/>
      <path d="M16 8a1 1 0 0 1 1 1v8a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4V9a1 1 0 0 1 1-1h12Z"/>
      <path d="M16 8h2a2 2 0 0 1 0 4h-2"/>
    </g>`,
  restaurant: `<g fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M3 2v7c0 1.1.9 2 2 2h4a2 2 0 0 0 2-2V2"/>
      <path d="M7 2v20"/>
      <path d="M21 15V2a5 5 0 0 0-5 5v6c0 1.1.9 2 2 2h3Zm0 0v7"/>
    </g>`,
  shopping: `<g fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <circle cx="8" cy="21" r="1"/>
      <circle cx="19" cy="21" r="1"/>
      <path d="M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 1.95-1.57l1.65-7.43H5.12"/>
    </g>`,
}

export function nearbyPlaceIconDataUrl(kind: NearbyPlaceKind): string {
  const color = NEARBY_PLACE_META[kind].color
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 40 40">
    <circle cx="20" cy="20" r="18" fill="${color}" stroke="#ffffff" stroke-width="3"/>
    <g transform="translate(8 8)">${MARKER_ICON_INNER[kind]}</g>
  </svg>`
  return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`
}

export function createNearbyPlaceMarkerElement(
  kind: NearbyPlaceKind,
  featured = false
): HTMLImageElement {
  const img = document.createElement("img")
  img.src = nearbyPlaceIconDataUrl(kind)
  img.alt = NEARBY_PLACE_META[kind].label
  const size = featured ? 48 : 40
  img.width = size
  img.height = size
  img.draggable = false
  img.style.display = "block"
  img.style.width = `${size}px`
  img.style.height = `${size}px`
  img.style.cursor = "pointer"
  img.style.filter = featured
    ? "drop-shadow(0 0 6px rgba(250,204,21,0.95)) drop-shadow(0 2px 4px rgba(0,0,0,0.35))"
    : "drop-shadow(0 2px 4px rgba(0,0,0,0.35))"
  return img
}

const SEARCH_TYPES: Array<{ type: string; kind: NearbyPlaceKind }> = [
  { type: "restaurant", kind: "restaurant" },
  { type: "cafe", kind: "cafe" },
  { type: "shopping_mall", kind: "shopping" },
  { type: "store", kind: "shopping" },
]

function classifyPlace(
  types: string[] | undefined,
  fallback: NearbyPlaceKind
): NearbyPlaceKind {
  const set = new Set(types ?? [])
  if (set.has("cafe")) return "cafe"
  if (set.has("restaurant") || set.has("meal_takeaway") || set.has("food")) {
    return "restaurant"
  }
  if (set.has("shopping_mall") || set.has("store") || set.has("clothing_store")) {
    return "shopping"
  }
  return fallback
}

function mapPlaceResult(
  place: google.maps.places.PlaceResult,
  fallbackKind: NearbyPlaceKind,
  center: GeoPoint
): NearbyPlace | null {
  const loc = place.geometry?.location
  const id = place.place_id
  const name = place.name
  if (!loc || !id || !name) return null

  const openNow =
    place.opening_hours?.open_now ??
    (place as { current_opening_hours?: { open_now?: boolean } }).current_opening_hours
      ?.open_now ??
    null

  const lat = loc.lat()
  const lng = loc.lng()
  const reviews = place.user_ratings_total

  return {
    id,
    name,
    kind: classifyPlace(place.types, fallbackKind),
    lat,
    lng,
    rating: typeof place.rating === "number" ? place.rating : undefined,
    openNow,
    vicinity: place.vicinity,
    userRatingCount: typeof reviews === "number" ? reviews : undefined,
    distanceMeters: haversineKm(center, { lat, lng }) * 1000,
  }
}

function nearbySearchOnce(
  service: google.maps.places.PlacesService,
  center: GeoPoint,
  type: string
): Promise<google.maps.places.PlaceResult[]> {
  return new Promise((resolve) => {
    service.nearbySearch(
      {
        location: { lat: center.lat, lng: center.lng },
        radius: NEARBY_SEARCH_RADIUS_M,
        type,
      },
      (results, status) => {
        const ok = window.google?.maps?.places?.PlacesServiceStatus
        if (status === ok?.ZERO_RESULTS || !results) {
          resolve([])
          return
        }
        if (status !== ok?.OK) {
          console.warn("[Places] nearbySearch", type, status)
          resolve([])
          return
        }
        resolve(results)
      }
    )
  })
}

/** 以充電站為中心，500 公尺內搜尋餐廳、咖啡廳、購物點 */
export async function searchNearbyAmenities(
  map: google.maps.Map,
  center: GeoPoint
): Promise<NearbyPlace[]> {
  const PlacesService = window.google?.maps?.places?.PlacesService
  if (typeof PlacesService !== "function") {
    throw new Error("PlacesService 尚未載入")
  }

  const service = new PlacesService(map)
  const batches = await Promise.all(
    SEARCH_TYPES.map(async ({ type, kind }) => {
      const rows = await nearbySearchOnce(service, center, type)
      return rows
        .map((row) => mapPlaceResult(row, kind, center))
        .filter((row): row is NearbyPlace => row != null)
    })
  )

  const byId = new Map<string, NearbyPlace>()
  for (const place of batches.flat()) {
    const existing = byId.get(place.id)
    if (!existing) {
      byId.set(place.id, place)
      continue
    }
    const rank = { cafe: 3, restaurant: 2, shopping: 1 }
    if (rank[place.kind] > rank[existing.kind]) byId.set(place.id, place)
  }

  return [...byId.values()].sort((a, b) => (b.rating ?? 0) - (a.rating ?? 0))
}
