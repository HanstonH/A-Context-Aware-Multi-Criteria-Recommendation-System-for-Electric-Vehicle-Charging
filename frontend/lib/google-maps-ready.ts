"use client"

import { useEffect, useState } from "react"

/** Google Maps JS API 是否已掛上 window（繪製標記前必須通過） */
export function isGoogleMapsApiLoaded(): boolean {
  if (typeof window === "undefined") return false
  const maps = window.google?.maps
  return Boolean(maps && typeof maps === "object")
}

/** 等到 window.google.maps 可用；逾時或載入失敗則維持 false，呼叫端應停止繪製 */
export function useGoogleMapsReady(): boolean {
  const [ready, setReady] = useState(false)

  useEffect(() => {
    if (isGoogleMapsApiLoaded()) {
      setReady(true)
      return
    }

    let cancelled = false
    const check = () => {
      if (cancelled) return false
      if (!isGoogleMapsApiLoaded()) return false
      setReady(true)
      return true
    }

    const intervalId = window.setInterval(() => {
      if (check()) window.clearInterval(intervalId)
    }, 100)

    const timeoutId = window.setTimeout(() => {
      window.clearInterval(intervalId)
    }, 20000)

    return () => {
      cancelled = true
      window.clearInterval(intervalId)
      window.clearTimeout(timeoutId)
    }
  }, [])

  return ready
}

export type MapOverlayLike = {
  setMap?: ((map: google.maps.Map | null) => void) | null
  remove?: (() => void) | null
} | null

/** 安全卸除地圖 overlay：相容 classic Marker.setMap(null) 與 AdvancedMarkerElement.remove() */
export function safeClearMapOverlay(overlay: MapOverlayLike | undefined): void {
  if (!overlay) return
  overlay.setMap?.(null)
  overlay.remove?.()
}

export type RemovableListener = {
  remove?: (() => void) | null
} | null

export function safeRemoveListener(listener: RemovableListener | undefined): void {
  listener?.remove?.()
}
