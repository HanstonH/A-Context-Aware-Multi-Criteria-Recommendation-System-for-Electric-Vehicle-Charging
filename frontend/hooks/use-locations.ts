"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import {
  type Location,
  type MapBounds,
  computeMapBoundsFromChargers,
  fetchLocationsFromSupabase,
  mergeAllLocations,
  simulateLocationAvailability,
} from "@/lib/locations"
import { fetchStationsFromExpress } from "@/lib/api/stations"
import type { GeoPoint } from "@/lib/map-coords"

export type LocationSource = "express" | "supabase"

function chargerCount(items: Location[]): number {
  return items.filter((item) => item.type === "ev-charger").length
}

export function useLocations() {
  const [locations, setLocations] = useState<Location[]>([])
  const [mapBounds, setMapBounds] = useState<MapBounds | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sourceWarning, setSourceWarning] = useState<string | null>(null)
  const [emptyHint, setEmptyHint] = useState<string | null>(null)
  const [source, setSource] = useState<LocationSource>("supabase")
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  const lastSuccessfulChargersRef = useRef<Location[]>([])
  const requestSeqRef = useRef(0)

  const applyStations = useCallback((evChargers: Location[], center: GeoPoint | null) => {
    if (evChargers.length === 0) {
      if (lastSuccessfulChargersRef.current.length > 0) {
        setLocations(mergeAllLocations(lastSuccessfulChargersRef.current))
        setMapBounds(computeMapBoundsFromChargers(lastSuccessfulChargersRef.current))
        setEmptyHint(null)
        return
      }
      setLocations(mergeAllLocations([]))
      setMapBounds(null)
      setEmptyHint("暫無充電站")
      return
    }

    lastSuccessfulChargersRef.current = evChargers
    setEmptyHint(null)
    setLocations(mergeAllLocations(evChargers))
    setMapBounds(computeMapBoundsFromChargers(evChargers))
    setLastUpdated(new Date())
  }, [])

  const load = useCallback(
    async (opts?: { silent?: boolean; center?: GeoPoint | null }) => {
      const center = opts?.center ?? null
      const seq = ++requestSeqRef.current

      if (opts?.silent) {
        setIsRefreshing(true)
      } else {
        setIsLoading(true)
      }
      setError(null)
      setSourceWarning(null)

      try {
        const evChargers = await fetchLocationsFromSupabase()
        if (seq !== requestSeqRef.current) return
        applyStations(evChargers, center)
        setSource("supabase")
      } catch (supabaseError) {
        try {
          const result = await fetchStationsFromExpress()
          if (seq !== requestSeqRef.current) return
          applyStations(result.locations, center)
          setSource("express")
          const supabaseMessage =
            supabaseError instanceof Error ? supabaseError.message : "Supabase 無法連線"
          setSourceWarning(`Supabase stations 無法使用，已改用 Express 備援。${supabaseMessage}`)
        } catch (e) {
          if (seq !== requestSeqRef.current) return
          const message = e instanceof Error ? e.message : "載入充電樁失敗"
          if (lastSuccessfulChargersRef.current.length > 0) {
            setLocations(mergeAllLocations(lastSuccessfulChargersRef.current))
            setMapBounds(computeMapBoundsFromChargers(lastSuccessfulChargersRef.current))
            setSourceWarning(message)
            setEmptyHint(null)
            return
          }
          if (!opts?.silent) {
            setError(supabaseError instanceof Error ? supabaseError.message : message)
            setEmptyHint("暫無充電站")
            return
          }
          setEmptyHint("暫無充電站")
          throw e instanceof Error ? e : new Error(message)
        }
      } finally {
        if (seq === requestSeqRef.current) {
          setIsLoading(false)
          setIsRefreshing(false)
        }
      }
    },
    [applyStations]
  )

  useEffect(() => {
    void load().catch(() => {
      /* 初始錯誤已寫入 error state */
    })
  }, [load])

  const reload = useCallback(async () => {
    await load({ silent: true })
  }, [load])

  const reloadNear = useCallback(
    async (center: GeoPoint) => {
      await load({ silent: true, center })
    },
    [load]
  )

  const simulateAvailability = useCallback(() => {
    setLocations((prev) => {
      const next = simulateLocationAvailability(prev)
      const chargers = next.filter((item) => item.type === "ev-charger")
      if (chargers.length > 0) lastSuccessfulChargersRef.current = chargers
      return next
    })
    setLastUpdated(new Date())
  }, [])

  const retry = useCallback(async () => {
    await load()
  }, [load])

  const defaultCenter: GeoPoint | null = mapBounds
    ? {
        lat: (mapBounds.north + mapBounds.south) / 2,
        lng: (mapBounds.east + mapBounds.west) / 2,
      }
    : null

  return {
    locations,
    setLocations,
    mapBounds,
    defaultCenter,
    isLoading,
    isRefreshing,
    error,
    sourceWarning,
    emptyHint,
    hasChargers: chargerCount(locations) > 0 || lastSuccessfulChargersRef.current.length > 0,
    source,
    lastUpdated,
    reload,
    reloadNear,
    retry,
    simulateAvailability,
  }
}
