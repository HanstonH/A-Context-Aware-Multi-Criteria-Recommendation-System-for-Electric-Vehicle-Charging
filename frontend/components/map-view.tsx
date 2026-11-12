"use client"

import { useCallback, useEffect, useState } from "react"
import {
  InfoWindow,
  Map,
  useMap,
  useMapsLibrary,
} from "@vis.gl/react-google-maps"
import {
  Crosshair,
  LocateFixed,
  Navigation,
  Zap,
  CornerUpLeft,
  AlertTriangle,
  CircleDollarSign,
  RefreshCw,
  Shuffle,
  Loader2,
  Sparkles,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { aura } from "@/lib/aura-styles"
import { Badge } from "@/components/ui/badge"
import { type GeoPoint, formatLatLng } from "@/lib/map-coords"
import {
  filterStationsForRange,
  type ChargingStation,
} from "@/lib/charging-stations"
import { formatChargerPrice, formatStationSchemaDetails } from "@/lib/locations"
import { AiChatPanel } from "@/components/ai-chat-panel"
import { StationMarkerCluster } from "@/components/station-marker-cluster"
import { NearbyPlacesLayer, NearbyPlacesList } from "@/components/nearby-places-layer"
import type { NearbyPlace } from "@/lib/nearby-places"
import { DirectionsRouteLayer } from "@/components/directions-route-layer"
import type { RouteSummary } from "@/lib/ai/route-types"
import {
  AvailabilityLegend,
  StationAvailabilityCard,
} from "@/components/charger-availability"
import { toast } from "sonner"
import {
  isGoogleMapsApiLoaded,
  useGoogleMapsReady,
} from "@/lib/google-maps-ready"
import { HIDE_NATIVE_POI_STYLES } from "@/lib/google-map-styles"

const GOOGLE_MAPS_API_KEY =
  process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY || process.env.GOOGLE_MAPS_API_KEY || ""
const GOOGLE_MAP_ID = process.env.NEXT_PUBLIC_GOOGLE_MAP_ID || "DEMO_MAP_ID"

const demoStations = [
  {
    id: "demo-01",
    name: "演示用充電站 (台北車站)",
    latitude: 25.0478,
    longitude: 121.517,
    status: "可用",
    power: "120kW",
  },
] as const

const DEMO_MAP_CENTER = {
  lat: demoStations[0].latitude,
  lng: demoStations[0].longitude,
}

function toDemoChargingStation(
  station: (typeof demoStations)[number]
): ChargingStation {
  const latitude = Number(station.latitude)
  const longitude = Number(station.longitude)
  return {
    id: station.id,
    station_name: station.name,
    name: station.name,
    address: "台北市中正區北平西路 3 號（演示）",
    chargerType: "DC",
    typeLabel: station.power,
    price: 0,
    available: 2,
    totalChargers: 4,
    availableChargers: 2,
    stationStatus: "online",
    portAvailability: [{ type: "CCS2", total: 4, available: 2 }],
    latitude,
    longitude,
    lat: latitude,
    lng: longitude,
  }
}

function stationLatLng(station?: ChargingStation | null): { lat: number; lng: number } | null {
  const lat = Number(station?.latitude ?? station?.lat)
  const lng = Number(station?.longitude ?? station?.lng)
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null
  return { lat, lng }
}

function stationTitle(station?: ChargingStation | null): string {
  return station?.station_name ?? station?.name ?? "未命名充電站"
}

function mergeDemoStations(stations: ChargingStation[]): ChargingStation[] {
  const demoMapped = demoStations.map(toDemoChargingStation)
  const existingIds = new Set(stations.map((s) => String(s.id)))
  return [...demoMapped.filter((s) => !existingIds.has(String(s.id))), ...stations]
}

interface MapViewProps {
  chargingStations: ChargingStation[]
  selectedDestination: string | null
  isNavigating: boolean
  currentLocation: GeoPoint | null
  onRequestGps?: () => void
  isGpsLocating?: boolean
  lowBatteryMode: boolean
  flyToToken: number
  onRefresh?: () => Promise<void> | void
  onSimulate?: () => void
  isRefreshing?: boolean
  lastUpdated?: Date | null
  flyToTarget?: GeoPoint | null
  dataSourceLabel?: string
  isRecommendLoading?: boolean
  onNearbyPlacesChange?: (payload: {
    stationName: string | null
    places: NearbyPlace[]
    loading: boolean
  }) => void
  focusedNearbyPlace?: NearbyPlace | null
  batteryPercent?: number
  routeDestination?: GeoPoint | null
  onRouteChange?: (summary: RouteSummary | null) => void
}

/** JSON styles 在設了 mapId 時會被忽略，改套 StyledMapType 隱藏原生 POI */
function HideNativePoiStyles() {
  const map = useMap()

  useEffect(() => {
    if (!map || !isGoogleMapsApiLoaded()) return
    const maps = window.google?.maps
    if (!maps) return

    map.setOptions({
      clickableIcons: false,
      styles: HIDE_NATIVE_POI_STYLES,
    })

    if (typeof maps.StyledMapType !== "function") return

    const styled = new maps.StyledMapType(HIDE_NATIVE_POI_STYLES, {
      name: "No native POI",
    })
    map.mapTypes.set("no_native_poi", styled)
    map.setMapTypeId("no_native_poi")
  }, [map])

  return null
}

function MapFlyTo({ position, token }: { position: GeoPoint; token: number }) {
  const map = useMap()
  useEffect(() => {
    if (!map || token <= 0 || !isGoogleMapsApiLoaded()) return
    map.panTo?.(position)
    map.setZoom?.(14)
  }, [map, position, token])
  return null
}

function VirtualLocationMarker({ position }: { position: GeoPoint | null }) {
  const map = useMap()
  const markerLib = useMapsLibrary("marker")

  useEffect(() => {
    if (!map || !markerLib || !position) return
    const AdvancedMarkerElement = markerLib.AdvancedMarkerElement
    if (typeof AdvancedMarkerElement !== "function") return
    const PinElement = markerLib.PinElement
    const pin =
      typeof PinElement === "function"
        ? new PinElement({
            background: "#0284c7",
            borderColor: "#ffffff",
            glyphColor: "#ffffff",
            scale: 1.15,
          })
        : null

    const marker = new AdvancedMarkerElement({
      map,
      position,
      title: "GPS 定位",
      zIndex: 2000,
      ...(pin ? { content: pin.element } : {}),
    })

    return () => {
      marker.map = null
    }
  }, [map, markerLib, position?.lat, position?.lng])

  return null
}

function StationInfoWindow({
  station,
  lowBatteryMode,
  onClose,
}: {
  station: ChargingStation
  lowBatteryMode: boolean
  onClose: () => void
}) {
  const schemaLines = formatStationSchemaDetails(station)
  const coords = stationLatLng(station)
  if (!coords) return null
  return (
    <InfoWindow
      position={coords}
      onCloseClick={onClose}
      maxWidth={340}
    >
      <div className="p-1 min-w-[280px]">
        <h3 className="font-bold text-base text-gray-900 leading-snug pr-2">
          {stationTitle(station)}
        </h3>
        <p className="text-sm text-gray-600 mt-1">{station?.address || "—"}</p>
        <p className="text-[11px] font-mono text-gray-500 mt-1">
          {formatLatLng(coords)}
        </p>
        {schemaLines.length > 0 && (
          <ul className="mt-2 space-y-0.5 text-xs text-gray-600">
            {schemaLines.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        )}
        <div className="flex flex-wrap gap-1.5 mt-3">
          <Badge className="rounded-md text-[11px] bg-amber-100 text-amber-900 border-0">
            <Zap className="w-3 h-3 mr-0.5" />
            {station.typeLabel}
          </Badge>
          <Badge className="rounded-md text-[11px] bg-emerald-100 text-emerald-900 border-0">
            <CircleDollarSign className="w-3 h-3 mr-0.5" />
            {formatChargerPrice(station.price)}
          </Badge>
        </div>
        <StationAvailabilityCard
          className="mt-3"
          available={station.availableChargers}
          total={station.totalChargers}
          status={station.stationStatus}
          ports={station.portAvailability}
        />
        {station.isRecommended && (
          <p className="text-xs text-violet-700 font-semibold mt-2">
            <Sparkles className="w-3 h-3 inline mr-1" />
            {station.recommendRank ? `AI 推薦 #${station.recommendRank}` : "AI 推薦"}
            {station.recommendReason ? ` · ${station.recommendReason}` : ""}
          </p>
        )}
        {lowBatteryMode && station.chargerType === "DC" && !station.isRecommended && (
          <p className="text-xs text-red-600 font-semibold mt-2">⚡ 低電量優先推薦快充</p>
        )}
      </div>
    </InfoWindow>
  )
}

function GoogleMapInner({
  chargingStations,
  selectedDestination,
  isNavigating,
  currentLocation,
  onRequestGps,
  isGpsLocating = false,
  lowBatteryMode,
  flyToToken,
  onRefresh,
  onSimulate,
  isRefreshing = false,
  lastUpdated,
  flyToTarget,
  dataSourceLabel,
  isRecommendLoading = false,
  onNearbyPlacesChange,
  focusedNearbyPlace = null,
  batteryPercent = 80,
  routeDestination = null,
  onRouteChange,
}: MapViewProps) {
  const mapsReady = useGoogleMapsReady()
  const [selectedStation, setSelectedStation] = useState<ChargingStation | null>(null)
  const [nearbyPlaces, setNearbyPlaces] = useState<NearbyPlace[]>([])
  const [nearbyLoading, setNearbyLoading] = useState(false)
  const [selectedNearbyPlace, setSelectedNearbyPlace] = useState<NearbyPlace | null>(null)
  const [localFlyCounter, setLocalFlyCounter] = useState(0)
  const [mapsLoadFailed, setMapsLoadFailed] = useState(false)
  const stationsWithDemo = mergeDemoStations(chargingStations)
  const recommendedActive = stationsWithDemo.some((s) => s.isRecommended)
  const visibleStations = [...filterStationsForRange(stationsWithDemo, lowBatteryMode, recommendedActive)]
    .map((station) => {
      const coords = stationLatLng(station)
      if (!coords) return null
      return {
        ...station,
        latitude: coords.lat,
        longitude: coords.lng,
        lat: coords.lat,
        lng: coords.lng,
        station_name: stationTitle(station),
      }
    })
    .filter((station): station is ChargingStation => station != null)
    .sort((a, b) => Number(Boolean(a.isRecommended)) - Number(Boolean(b.isRecommended)))
  const flyTarget = flyToTarget ?? currentLocation

  useEffect(() => {
    console.log("成功渲染地圖標記數：", visibleStations.length)
  }, [visibleStations.length])

  useEffect(() => {
    if (!selectedDestination) return
    const match = visibleStations.find(
      (station) =>
        station?.station_name === selectedDestination || station?.name === selectedDestination
    )
    if (match) setSelectedStation(match)
  }, [selectedDestination])

  const selectedCoords = stationLatLng(selectedStation)
  const selectedStationName = selectedStation ? stationTitle(selectedStation) : null

  useEffect(() => {
    onNearbyPlacesChange?.({
      stationName: selectedStationName,
      places: nearbyPlaces,
      loading: nearbyLoading,
    })
  }, [selectedStationName, nearbyPlaces, nearbyLoading, onNearbyPlacesChange])

  useEffect(() => {
    if (focusedNearbyPlace) setSelectedNearbyPlace(focusedNearbyPlace)
  }, [focusedNearbyPlace])

  const handleSelectStation = useCallback((station: ChargingStation) => {
    setSelectedStation(station)
    setSelectedNearbyPlace(null)
  }, [])

  useEffect(() => {
    if (mapsReady) {
      setMapsLoadFailed(false)
      return
    }
    const timeoutId = window.setTimeout(() => {
      if (!isGoogleMapsApiLoaded()) setMapsLoadFailed(true)
    }, 20000)
    return () => window.clearTimeout(timeoutId)
  }, [mapsReady])

  const handleLocate = useCallback(() => {
    if (onRequestGps) {
      onRequestGps()
      return
    }
    setLocalFlyCounter((c) => c + 1)
  }, [onRequestGps])

  const handleRefresh = useCallback(async () => {
    if (!onRefresh) return
    try {
      await onRefresh()
      toast.success("已重新載入最新空槍狀態")
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "刷新失敗，請稍後再試")
    }
  }, [onRefresh])

  const handleSimulate = useCallback(() => {
    onSimulate?.()
    toast.message("已模擬即時空槍更新", {
      description: "觀察地圖燈號與數字標籤的變化",
    })
  }, [onSimulate])

  const updatedLabel = lastUpdated
    ? lastUpdated.toLocaleTimeString("zh-TW", { hour: "2-digit", minute: "2-digit", second: "2-digit" })
    : null

  return (
    <div className="relative w-full h-full">
      <Map
        defaultCenter={DEMO_MAP_CENTER}
        defaultZoom={14}
        gestureHandling="greedy"
        mapId={GOOGLE_MAP_ID}
        className="w-full h-full"
        disableDefaultUI={false}
        clickableIcons={false}
        styles={HIDE_NATIVE_POI_STYLES}
      >
        {mapsReady && <HideNativePoiStyles />}
        {mapsReady && flyTarget && (
          <MapFlyTo position={flyTarget} token={flyToToken + localFlyCounter} />
        )}
        {mapsReady && <VirtualLocationMarker position={currentLocation} />}
        {mapsReady && (
          <StationMarkerCluster
            stations={visibleStations}
            onSelect={handleSelectStation}
          />
        )}
        {mapsReady && (
          <NearbyPlacesLayer
            center={selectedCoords}
            stationKey={selectedStation?.id ?? null}
            places={nearbyPlaces}
            loading={nearbyLoading}
            selectedPlace={selectedNearbyPlace}
            onPlacesChange={setNearbyPlaces}
            onLoadingChange={setNearbyLoading}
            onSelectPlace={setSelectedNearbyPlace}
            batteryPercent={batteryPercent}
            isUrgent={lowBatteryMode}
          />
        )}
        {mapsReady && (
          <DirectionsRouteLayer
            origin={currentLocation}
            destination={
              focusedNearbyPlace
                ? { lat: focusedNearbyPlace.lat, lng: focusedNearbyPlace.lng }
                : routeDestination ?? selectedCoords
            }
            enabled={Boolean(
              currentLocation &&
                (focusedNearbyPlace || routeDestination || selectedCoords)
            )}
            emphasized={isNavigating}
            onRouteChange={onRouteChange}
          />
        )}

        {mapsReady && selectedStation && stationLatLng(selectedStation) && (
            <StationInfoWindow
              station={selectedStation}
              lowBatteryMode={lowBatteryMode}
              onClose={() => {
                setSelectedStation(null)
                setNearbyPlaces([])
                setSelectedNearbyPlace(null)
                setNearbyLoading(false)
              }}
            />
          )}
      </Map>

      {mapsLoadFailed && !mapsReady && (
        <div className="absolute inset-0 z-20 flex flex-col items-center justify-center gap-2 bg-background/80 p-6 text-center">
          <Navigation className="w-10 h-10 text-muted-foreground" />
          <p className="font-semibold text-foreground">Google Maps 未能載入</p>
          <p className="text-sm text-muted-foreground max-w-md">
            已停止繪製標記，避免畫面崩潰。請確認 API Key、網路連線，以及 Maps JavaScript API 已啟用後重新整理。
          </p>
        </div>
      )}

      <div
        className={cn(
          "absolute top-4 right-4 z-10 rounded-2xl px-4 py-3 text-xs max-w-[220px] pointer-events-none",
          aura.glassCard,
          "shadow-lg"
        )}
      >
        <p className="text-muted-foreground font-medium flex items-center gap-1">
          <LocateFixed className="w-3.5 h-3.5 text-sky-600" />
          GPS 目前位置
        </p>
        <p className="font-mono text-foreground font-semibold mt-1">
          {currentLocation ? formatLatLng(currentLocation) : isGpsLocating ? "定位中…" : "尚未取得 GPS"}
        </p>
        <p className="text-[10px] text-muted-foreground mt-1">
          {currentLocation ? "由瀏覽器定位取得真實座標" : "請允許瀏覽器存取位置"}
        </p>
      </div>

      {isRecommendLoading && (
        <div
          className={cn(
            "absolute top-4 left-4 right-48 z-10 flex items-center gap-2 text-sm font-semibold",
            aura.glassCard,
            "shadow-lg"
          )}
        >
          <Loader2 className="w-4 h-4 shrink-0 animate-spin text-violet-600" />
          AI 正在依位置與電量計算最佳充電站…
        </div>
      )}

      {!isRecommendLoading && recommendedActive && (
        <div
          className={cn(
            "absolute top-4 left-4 right-48 z-10 flex items-center gap-2 text-sm font-semibold pointer-events-none",
            "rounded-xl bg-violet-500/10 backdrop-blur-sm border border-violet-400/30 text-violet-700 dark:text-violet-300 px-3 py-2 shadow-sm"
          )}
        >
          <Sparkles className="w-4 h-4 shrink-0" />
          已標出 AI 推薦充電站，可點擊地圖圖標查看原因
        </div>
      )}

      {!isRecommendLoading && !recommendedActive && lowBatteryMode && (
        <div
          className={cn(
            "absolute top-4 left-4 right-48 z-10 flex items-center gap-2 text-sm font-semibold pointer-events-none",
            aura.alertLowBattery,
            "shadow-lg"
          )}
        >
          <AlertTriangle className="w-4 h-4 shrink-0" />
          電量較低，已優先為您篩選高功率快充站！
        </div>
      )}

      {selectedStation && (
        <div
          className={cn(
            "absolute bottom-24 left-4 z-10 w-[min(calc(100%-2rem),320px)] max-h-[38vh] overflow-y-auto rounded-2xl p-3 shadow-xl",
            aura.glassCard
          )}
        >
          <NearbyPlacesList
            stationName={selectedStationName}
            places={nearbyPlaces}
            loading={nearbyLoading}
            selectedPlaceId={selectedNearbyPlace?.id}
            onSelect={setSelectedNearbyPlace}
          />
        </div>
      )}

      {isNavigating && selectedDestination && (
        <div
          className={cn(
            "absolute top-20 left-4 rounded-2xl p-4 z-10 max-w-xs shadow-xl pointer-events-none",
            aura.glassCard
          )}
        >
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-emerald-500 to-emerald-700 flex items-center justify-center">
              <CornerUpLeft className="w-6 h-6 text-white" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">下一步</p>
              <p className="font-semibold text-foreground">200 公尺後右轉</p>
            </div>
          </div>
        </div>
      )}

      <div
        className={cn(
          "absolute bottom-6 left-4 z-10 rounded-xl px-3 py-2 text-xs font-medium pointer-events-none max-w-[240px]",
          aura.glassCard
        )}
      >
        <p>
          <span className="text-emerald-600 font-bold">{visibleStations.length}</span>
          <span className="text-muted-foreground ml-1">
            {dataSourceLabel ?? "充電站"}
          </span>
        </p>
        {updatedLabel && (
          <p className="text-[10px] text-muted-foreground mt-0.5">更新於 {updatedLabel}</p>
        )}
        <AvailabilityLegend className="mt-1.5" />
      </div>

      <div className="absolute bottom-6 right-6 z-50 flex flex-col items-end space-y-3">
        {onSimulate && (
          <button
            type="button"
            onClick={handleSimulate}
            className={cn(
              "h-12 px-3 rounded-2xl flex items-center gap-2 text-xs font-bold",
              aura.btnGhost,
              "shadow-lg"
            )}
            aria-label="模擬即時更新"
            title="模擬即時空槍數量變化"
          >
            <Shuffle className="w-5 h-5 text-amber-600" />
            模擬更新
          </button>
        )}
        {onRefresh && (
          <button
            type="button"
            onClick={() => void handleRefresh()}
            disabled={isRefreshing}
            className={cn(
              "h-12 px-3 rounded-2xl flex items-center gap-2 text-xs font-bold",
              aura.btnGhost,
              "shadow-lg disabled:opacity-60"
            )}
            aria-label="手動刷新數據"
            title="重新向 Supabase 撈取最新狀態"
          >
            {isRefreshing ? (
              <Loader2 className="w-5 h-5 text-emerald-600 animate-spin" />
            ) : (
              <RefreshCw className="w-5 h-5 text-emerald-600" />
            )}
            {isRefreshing ? "刷新中" : "刷新數據"}
          </button>
        )}
        <AiChatPanel stacked />
        <button
          type="button"
          onClick={handleLocate}
          disabled={isGpsLocating}
          className={cn(
            "w-14 h-14 rounded-2xl flex items-center justify-center shrink-0",
            aura.fab,
            "disabled:opacity-70"
          )}
          aria-label="使用 GPS 定位"
          title="使用瀏覽器真實 GPS 定位"
        >
          {isGpsLocating ? (
            <Loader2 className="w-7 h-7 animate-spin" />
          ) : (
            <Crosshair className="w-7 h-7" />
          )}
        </button>
      </div>
    </div>
  )
}

export function MapView(props: MapViewProps) {
  if (!GOOGLE_MAPS_API_KEY || GOOGLE_MAPS_API_KEY === "YOUR_GOOGLE_KEY") {
    return (
      <div className="w-full h-full flex flex-col items-center justify-center gap-3 bg-muted/30 p-8 text-center">
        <Navigation className="w-12 h-12 text-emerald-600" />
        <h2 className="font-bold text-lg">請設定 Google Maps API Key</h2>
        <p className="text-sm text-muted-foreground max-w-md">
          在 <code className="text-xs bg-muted px-1 rounded">.env.local</code> 加入{" "}
          <code className="text-xs bg-muted px-1 rounded">NEXT_PUBLIC_GOOGLE_MAPS_API_KEY</code>
          ，並在 Google Cloud Console 啟用 Maps JavaScript API。
        </p>
        <p className="text-xs text-muted-foreground">
          建議另設 <code className="bg-muted px-1 rounded">NEXT_PUBLIC_GOOGLE_MAP_ID</code>{" "}
          以顯示客製化充電樁圖標。
        </p>
      </div>
    )
  }

  return <GoogleMapInner {...props} />
}
