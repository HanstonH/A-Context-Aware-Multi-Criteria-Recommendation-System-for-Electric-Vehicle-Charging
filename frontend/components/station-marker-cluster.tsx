"use client"

import { useEffect, useRef } from "react"
import { useMap, useMapsLibrary } from "@vis.gl/react-google-maps"
import { MarkerClusterer } from "@googlemaps/markerclusterer"
import type { ChargingStation } from "@/lib/charging-stations"
import {
  AVAILABILITY_THEME,
  getAvailabilityLight,
} from "@/lib/charger-availability"

function stationLatLng(station?: ChargingStation | null): { lat: number; lng: number } | null {
  const lat = Number(station?.latitude ?? station?.lat)
  const lng = Number(station?.longitude ?? station?.lng)
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null
  return { lat, lng }
}

function stationTitle(station?: ChargingStation | null): string {
  return station?.station_name ?? station?.name ?? "未命名充電站"
}

/**
 * 以 AdvancedMarkerElement 建立標記，交給 MarkerClusterer 管理，
 * 避免 3000+ 個 React DOM 標記一次掛上地圖。
 */
export function StationMarkerCluster({
  stations,
  onSelect,
}: {
  stations: ChargingStation[]
  onSelect: (station: ChargingStation) => void
}) {
  const map = useMap()
  const markerLib = useMapsLibrary("marker")
  const onSelectRef = useRef(onSelect)
  onSelectRef.current = onSelect

  const stationKey = stations
    .map((station) => {
      const coords = stationLatLng(station)
      return `${station?.id}:${coords?.lat}:${coords?.lng}`
    })
    .join("|")

  useEffect(() => {
    if (!map || !markerLib) return
    const AdvancedMarkerElement = markerLib.AdvancedMarkerElement
    if (typeof AdvancedMarkerElement !== "function") return
    const PinElement = markerLib.PinElement

    const markers: google.maps.marker.AdvancedMarkerElement[] = []

    for (const station of stations) {
      const coords = stationLatLng(station)
      if (!coords) continue

      const light = getAvailabilityLight(
        station?.availableChargers ?? 0,
        station?.totalChargers ?? 0,
        station?.stationStatus
      )
      const pin =
        typeof PinElement === "function"
          ? new PinElement({
              background: AVAILABILITY_THEME[light].markerBg,
              borderColor: "#ffffff",
              glyphColor: "#ffffff",
            })
          : null

      const marker = new AdvancedMarkerElement({
        position: coords,
        title: stationTitle(station),
        gmpClickable: true,
        ...(pin ? { content: pin.element } : {}),
      })

      marker.addListener("click", () => {
        onSelectRef.current(station)
      })
      markers.push(marker)
    }

    const clusterer = new MarkerClusterer({ map, markers })
    console.log("成功渲染地圖標記數：", markers.length)

    return () => {
      clusterer.clearMarkers()
      for (const marker of markers) {
        marker.map = null
      }
    }
  }, [map, markerLib, stationKey])

  return null
}
