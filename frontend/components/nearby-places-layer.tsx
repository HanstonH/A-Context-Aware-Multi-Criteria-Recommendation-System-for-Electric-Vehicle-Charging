"use client"

import { useEffect, useRef } from "react"
import { InfoWindow, useMap, useMapsLibrary } from "@vis.gl/react-google-maps"
import { Star, Clock, Store, Loader2 } from "lucide-react"
import { rankNearbyPlaces } from "@/lib/ai/recommend-places"
import {
  NEARBY_PLACE_META,
  createNearbyPlaceMarkerElement,
  searchNearbyAmenities,
  type NearbyPlace,
  type NearbyPlaceKind,
} from "@/lib/nearby-places"
import type { GeoPoint } from "@/lib/map-coords"

export function NearbyPlacesLayer({
  center,
  stationKey,
  places,
  loading,
  selectedPlace,
  onPlacesChange,
  onLoadingChange,
  onSelectPlace,
  batteryPercent = 80,
  isUrgent = false,
}: {
  center: GeoPoint | null
  stationKey: string | number | null
  places: NearbyPlace[]
  loading: boolean
  selectedPlace: NearbyPlace | null
  onPlacesChange: (places: NearbyPlace[]) => void
  onLoadingChange: (loading: boolean) => void
  onSelectPlace: (place: NearbyPlace | null) => void
  batteryPercent?: number
  isUrgent?: boolean
}) {
  const map = useMap()
  const markerLib = useMapsLibrary("marker")
  const placesLib = useMapsLibrary("places")
  const markersRef = useRef<google.maps.marker.AdvancedMarkerElement[]>([])
  const onSelectRef = useRef(onSelectPlace)
  const onPlacesChangeRef = useRef(onPlacesChange)
  const onLoadingChangeRef = useRef(onLoadingChange)
  onSelectRef.current = onSelectPlace
  onPlacesChangeRef.current = onPlacesChange
  onLoadingChangeRef.current = onLoadingChange

  useEffect(() => {
    if (!map || !placesLib) return

    if (!center || stationKey == null) {
      onPlacesChangeRef.current([])
      onLoadingChangeRef.current(false)
      onSelectRef.current(null)
      return
    }

    let cancelled = false
    onLoadingChangeRef.current(true)
    onPlacesChangeRef.current([])
    onSelectRef.current(null)

    void searchNearbyAmenities(map, center)
      .then((results) => {
        if (cancelled) return
        onPlacesChangeRef.current(rankNearbyPlaces(results, center, batteryPercent, isUrgent))
      })
      .catch((error) => {
        if (cancelled) return
        console.error("[Places] 周邊搜尋失敗:", error)
        onPlacesChangeRef.current([])
      })
      .finally(() => {
        if (!cancelled) onLoadingChangeRef.current(false)
      })

    return () => {
      cancelled = true
    }
  }, [map, placesLib, center?.lat, center?.lng, stationKey, batteryPercent, isUrgent])

  useEffect(() => {
    if (!map || !markerLib) return
    const AdvancedMarkerElement = markerLib.AdvancedMarkerElement
    if (typeof AdvancedMarkerElement !== "function") return

    const markers: google.maps.marker.AdvancedMarkerElement[] = []
    for (const place of places) {
      const marker = new AdvancedMarkerElement({
        map,
        position: { lat: place.lat, lng: place.lng },
        title: place.name,
        zIndex: place.isRecommended ? 3200 : 2500,
        gmpClickable: true,
        content: createNearbyPlaceMarkerElement(place.kind, Boolean(place.isRecommended)),
      })
      marker.addListener("click", () => onSelectRef.current(place))
      markers.push(marker)
    }
    markersRef.current = markers

    return () => {
      for (const marker of markers) {
        marker.map = null
      }
      markersRef.current = []
    }
  }, [map, markerLib, places])

  if (!selectedPlace) return null

  const meta = NEARBY_PLACE_META[selectedPlace.kind]
  const openLabel =
    selectedPlace.openNow === true
      ? "營業中"
      : selectedPlace.openNow === false
        ? "已打烊"
        : "營業狀態未知"

  return (
    <InfoWindow
      position={{ lat: selectedPlace.lat, lng: selectedPlace.lng }}
      onCloseClick={() => onSelectPlace(null)}
      maxWidth={280}
    >
      <div className="p-1 min-w-[220px]">
        <p className="text-[10px] font-semibold uppercase tracking-wide" style={{ color: meta.color }}>
          {meta.label}
        </p>
        <h3 className="font-bold text-sm text-gray-900 mt-0.5">{selectedPlace.name}</h3>
        {selectedPlace.isRecommended && (
          <p className="text-[11px] font-semibold text-amber-600 mt-1">
            AI 推薦 #{selectedPlace.recommendRank}
            {selectedPlace.recommendReason ? ` · ${selectedPlace.recommendReason}` : ""}
          </p>
        )}
        {selectedPlace.vicinity && (
          <p className="text-xs text-gray-500 mt-1">{selectedPlace.vicinity}</p>
        )}
        <div className="flex flex-wrap gap-2 mt-2 text-xs text-gray-700">
          <span className="inline-flex items-center gap-0.5">
            <Star className="w-3 h-3 text-amber-500" />
            {selectedPlace.rating != null ? selectedPlace.rating.toFixed(1) : "尚無評分"}
          </span>
          <span className="inline-flex items-center gap-0.5">
            <Clock className="w-3 h-3" />
            {openLabel}
          </span>
        </div>
      </div>
    </InfoWindow>
  )
}

export function NearbyPlacesList({
  stationName,
  places,
  loading,
  selectedPlaceId,
  onSelect,
}: {
  stationName?: string | null
  places: NearbyPlace[]
  loading: boolean
  selectedPlaceId?: string | null
  onSelect: (place: NearbyPlace) => void
}) {
  if (!stationName && !loading && places.length === 0) return null

  const groups: NearbyPlaceKind[] = ["restaurant", "cafe", "shopping"]

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Store className="w-4 h-4 text-emerald-600" />
        <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          周邊設施（500 公尺）
        </span>
      </div>
      {stationName && (
        <p className="text-xs text-muted-foreground">以「{stationName}」為中心</p>
      )}
      {loading && (
        <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground px-1 py-4">
          <Loader2 className="w-4 h-4 animate-spin text-emerald-600" />
          正在搜尋周邊設施…
        </div>
      )}
      {!loading && places.length === 0 && (
        <p className="text-sm text-muted-foreground px-1 py-3 text-center">附近沒有找到餐廳、咖啡廳或購物點</p>
      )}
      {!loading &&
        (() => {
          const recommended = places.filter((place) => place.isRecommended)
          const rest = places.filter((place) => !place.isRecommended)
          return (
            <>
              {recommended.length > 0 && (
                <div className="space-y-1.5">
                  <p className="text-[11px] font-bold text-amber-600">AI 推薦周邊 · {recommended.length}</p>
                  {recommended.map((place) => (
                    <button
                      key={place.id}
                      type="button"
                      onClick={() => onSelect(place)}
                      className={`w-full text-left rounded-xl px-3 py-2 text-sm border transition-colors ${
                        selectedPlaceId === place.id
                          ? "bg-white border-amber-400 shadow-sm"
                          : "bg-amber-50/80 dark:bg-amber-950/30 border-amber-300/60 hover:border-amber-400"
                      }`}
                    >
                      <p className="font-semibold text-foreground truncate">
                        #{place.recommendRank} {place.name}
                      </p>
                      <p className="text-[11px] text-muted-foreground mt-0.5">
                        {place.recommendReason ??
                          `${place.rating != null ? `★ ${place.rating.toFixed(1)}` : "尚無評分"}`}
                      </p>
                    </button>
                  ))}
                </div>
              )}
              {groups.map((kind) => {
                const rows = rest.filter((place) => place.kind === kind)
                if (rows.length === 0) return null
                const meta = NEARBY_PLACE_META[kind]
                return (
                  <div key={kind} className="space-y-1.5">
                    <p className="text-[11px] font-bold" style={{ color: meta.color }}>
                      {meta.label} · {rows.length}
                    </p>
                    {rows.map((place) => (
                      <button
                        key={place.id}
                        type="button"
                        onClick={() => onSelect(place)}
                        className={`w-full text-left rounded-xl px-3 py-2 text-sm border transition-colors ${
                          selectedPlaceId === place.id
                            ? "bg-white border-emerald-400 shadow-sm"
                            : "bg-white/70 dark:bg-zinc-900/50 border-white/40 dark:border-white/10 hover:border-emerald-300"
                        }`}
                      >
                        <p className="font-semibold text-foreground truncate">{place.name}</p>
                        <p className="text-[11px] text-muted-foreground mt-0.5">
                          {place.rating != null ? `★ ${place.rating.toFixed(1)}` : "尚無評分"}
                          {" · "}
                          {place.openNow === true
                            ? "營業中"
                            : place.openNow === false
                              ? "已打烊"
                              : "營業未知"}
                        </p>
                      </button>
                    ))}
                  </div>
                )
              })}
            </>
          )
        })()}
    </div>
  )
}
