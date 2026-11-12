"use client"

import { useEffect, useRef } from "react"
import { useMap, useMapsLibrary } from "@vis.gl/react-google-maps"
import type { GeoPoint } from "@/lib/map-coords"
import type { RouteSummary } from "@/lib/ai/route-types"

export function DirectionsRouteLayer({
  origin,
  destination,
  enabled,
  emphasized = false,
  onRouteChange,
}: {
  origin: GeoPoint | null
  destination: GeoPoint | null
  enabled: boolean
  emphasized?: boolean
  onRouteChange?: (summary: RouteSummary | null) => void
}) {
  const map = useMap()
  const mapsLib = useMapsLibrary("maps")
  const rendererRef = useRef<google.maps.DirectionsRenderer | null>(null)
  const onRouteChangeRef = useRef(onRouteChange)
  onRouteChangeRef.current = onRouteChange

  useEffect(() => {
    if (!map || !mapsLib || !enabled || !origin || !destination) {
      rendererRef.current?.setMap(null)
      rendererRef.current = null
      onRouteChangeRef.current?.(null)
      return
    }

    const DirectionsService = mapsLib.DirectionsService
    const DirectionsRenderer = mapsLib.DirectionsRenderer
    if (typeof DirectionsService !== "function" || typeof DirectionsRenderer !== "function") {
      return
    }

    const service = new DirectionsService()
    const renderer = new DirectionsRenderer({
      map,
      suppressMarkers: true,
      preserveViewport: !emphasized,
      polylineOptions: {
        strokeColor: emphasized ? "#059669" : "#34d399",
        strokeWeight: emphasized ? 6 : 5,
        strokeOpacity: emphasized ? 0.95 : 0.75,
      },
    })
    rendererRef.current = renderer

    service.route(
      {
        origin: { lat: origin.lat, lng: origin.lng },
        destination: { lat: destination.lat, lng: destination.lng },
        travelMode: google.maps.TravelMode.DRIVING,
        drivingOptions: {
          departureTime: new Date(),
          trafficModel: google.maps.TrafficModel.BEST_GUESS,
        },
        provideRouteAlternatives: false,
      },
      (result, status) => {
        if (status !== google.maps.DirectionsStatus.OK || !result?.routes?.[0]) {
          console.warn("[Directions] 路線計算失敗:", status)
          onRouteChangeRef.current?.(null)
          return
        }
        renderer.setDirections(result)
        const leg = result.routes[0].legs[0]
        onRouteChangeRef.current?.({
          durationText: leg?.duration?.text ?? "—",
          distanceText: leg?.distance?.text ?? "—",
          durationSeconds: leg?.duration?.value ?? 0,
          distanceMeters: leg?.distance?.value ?? 0,
          summary: result.routes[0].summary,
        })
      }
    )

    return () => {
      renderer.setMap(null)
      if (rendererRef.current === renderer) rendererRef.current = null
    }
  }, [map, mapsLib, enabled, origin?.lat, origin?.lng, destination?.lat, destination?.lng, emphasized])

  return null
}
