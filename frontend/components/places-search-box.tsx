"use client"

import { useEffect, useRef } from "react"
import { useMapsLibrary } from "@vis.gl/react-google-maps"
import { Search, X } from "lucide-react"
import { cn } from "@/lib/utils"
import { aura } from "@/lib/aura-styles"
import type { GeoPoint } from "@/lib/map-coords"
import { isGoogleMapsApiLoaded } from "@/lib/google-maps-ready"

export interface PlacePick {
  name: string
  location: GeoPoint
}

interface PlacesSearchBoxProps {
  onPlaceSelect: (place: PlacePick) => void
  placeholder?: string
  className?: string
  autoFocus?: boolean
}

type PlaceAutocompleteCtor = new (options?: {
  includedRegionCodes?: string[]
}) => HTMLElement & {
  addEventListener: HTMLElement["addEventListener"]
  removeEventListener: HTMLElement["removeEventListener"]
}

/** 上方搜尋：PlaceAutocompleteElement，只移動地圖，不觸發 AI */
export function PlacesSearchBox({
  onPlaceSelect,
  placeholder = "搜尋地點、地址…",
  className,
  autoFocus = false,
}: PlacesSearchBoxProps) {
  const places = useMapsLibrary("places")
  const hostRef = useRef<HTMLDivElement>(null)
  const onSelectRef = useRef(onPlaceSelect)
  onSelectRef.current = onPlaceSelect

  useEffect(() => {
    if (!places || !hostRef.current || !isGoogleMapsApiLoaded()) return

    const Ctor = (places as { PlaceAutocompleteElement?: PlaceAutocompleteCtor })
      .PlaceAutocompleteElement
    if (typeof Ctor !== "function") return

    const element = new Ctor({ includedRegionCodes: ["tw"] })
    element.setAttribute("placeholder", placeholder)
    element.style.width = "100%"
    if (autoFocus) {
      window.setTimeout(() => element.focus?.(), 0)
    }

    hostRef.current.replaceChildren(element)

    const handleSelect = async (event: Event) => {
      const detail = event as Event & {
        placePrediction?: {
          toPlace?: () => {
            fetchFields: (opts: { fields: string[] }) => Promise<void>
            displayName?: string
            formattedAddress?: string
            location?: google.maps.LatLng | null
          }
        }
        place?: google.maps.places.Place
      }

      try {
        const prediction = detail.placePrediction
        if (prediction?.toPlace) {
          const place = prediction.toPlace()
          await place.fetchFields({
            fields: ["displayName", "formattedAddress", "location"],
          })
          const loc = place.location
          if (!loc) return
          onSelectRef.current({
            name: place.displayName || place.formattedAddress || "地點",
            location: { lat: loc.lat(), lng: loc.lng() },
          })
          return
        }

        const legacy = detail.place
        if (legacy) {
          await legacy.fetchFields?.({
            fields: ["displayName", "formattedAddress", "location"],
          })
          const loc = legacy.location
          if (!loc) return
          onSelectRef.current({
            name: legacy.displayName || legacy.formattedAddress || "地點",
            location: { lat: loc.lat(), lng: loc.lng() },
          })
        }
      } catch (error) {
        console.error("[Places] 選取地點失敗:", error)
      }
    }

    element.addEventListener("gmp-select", handleSelect)
    element.addEventListener("gmp-placeselect", handleSelect)

    return () => {
      element.removeEventListener("gmp-select", handleSelect)
      element.removeEventListener("gmp-placeselect", handleSelect)
      hostRef.current?.replaceChildren()
    }
  }, [places, placeholder, autoFocus])

  return (
    <div className={cn("relative flex-1", className)}>
      <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-emerald-600 pointer-events-none z-10" />
      <div
        ref={hostRef}
        className={cn(aura.glassInset, "h-11 rounded-xl pl-9 pr-9 shadow-sm overflow-hidden")}
      />
      <button
        type="button"
        className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground z-10"
        onClick={(e) => {
          e.stopPropagation()
          const input = hostRef.current?.querySelector("input")
          if (input) input.value = ""
        }}
        aria-label="清除搜尋"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  )
}
