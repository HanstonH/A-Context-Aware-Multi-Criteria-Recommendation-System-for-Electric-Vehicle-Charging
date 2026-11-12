import { haversineKm } from "@/lib/map-coords"
import type { GeoPoint } from "@/lib/map-coords"
import type { NearbyPlace } from "@/lib/nearby-places"
import { topsisRank } from "@/lib/ai/topsis"
import { contextStateLabel } from "@/lib/ai/weights"

/** 對齊 `logic.py` `calculate_poi_score` */
export function calculatePoiScore(rating: number, reviews: number, distanceMeters: number): number {
  const safeRating = Number.isFinite(rating) ? rating : 0
  const safeReviews = Number.isFinite(reviews) ? Math.max(0, reviews) : 0
  const safeDistance = Number.isFinite(distanceMeters) ? Math.max(0, distanceMeters) : 500
  return (safeRating * Math.log10(safeReviews + 1)) / (1 + safeDistance / 100)
}

const TOP_N = 5

export function rankNearbyPlaces(
  places: NearbyPlace[],
  station: GeoPoint,
  batteryPercent: number,
  isAvailableNow = false
): NearbyPlace[] {
  if (places.length === 0) return places

  const enriched = places.map((place) => {
    const distanceMeters =
      place.distanceMeters ?? haversineKm(station, { lat: place.lat, lng: place.lng }) * 1000
    const poiScore = calculatePoiScore(place.rating ?? 0, place.userRatingCount ?? 0, distanceMeters)
    return {
      ...place,
      distanceMeters,
      poiScore,
      distance: distanceMeters,
      poiCount: poiScore,
      cost: 0,
      availablePots: place.openNow === true ? 2 : place.openNow === false ? 0 : 1,
      id: place.id,
    }
  })

  return ranked.map((row, index) => {
    const isRecommended = index < TOP_N
    return {
      id: row.id,
      name: row.name,
      kind: row.kind,
      lat: row.lat,
      lng: row.lng,
      rating: row.rating,
      openNow: row.openNow,
      vicinity: row.vicinity,
      userRatingCount: row.userRatingCount,
      distanceMeters: row.distanceMeters,
      recommendRank: isRecommended ? index + 1 : undefined,
      recommendScore: row.topsisScore,
      recommendReason: isRecommended
        ? `${state} 高優先 · 評分 ${row.rating?.toFixed(1) ?? "—"}`
        : undefined,
      isRecommended,
    }
  })
}
