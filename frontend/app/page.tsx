"use client"

import { useState, useEffect, useCallback } from "react"
import { APIProvider } from "@vis.gl/react-google-maps"
import { LoginScreen } from "@/components/screens/login-screen"
import { Sidebar } from "@/components/sidebar"
import { MapView } from "@/components/map-view"
import { Toaster, toast } from "sonner"
import { useLocations } from "@/hooks/use-locations"
import { useRecommend } from "@/hooks/use-recommend"
import type { GeoPoint } from "@/lib/map-coords"
import { locationsToChargingStations, LOW_BATTERY_THRESHOLD } from "@/lib/charging-stations"
import type { ChargingStation } from "@/lib/charging-stations"
import { applyRecommendations } from "@/lib/api/normalize"
import type { PlacePick } from "@/components/places-search-box"
import { Loader2 } from "lucide-react"
import type { NearbyPlace } from "@/lib/nearby-places"
import { findLocationByName } from "@/lib/locations"
import { locationsToRankInput, nearestStationInputs } from "@/lib/ai/recommend-stations"
import type { RouteSummary } from "@/lib/ai/route-types"

const GOOGLE_MAPS_API_KEY =
  process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY || process.env.GOOGLE_MAPS_API_KEY || ""

export default function MapExplorePage() {
  const [isLoggedIn, setIsLoggedIn] = useState(false)
  const [selectedDestination, setSelectedDestination] = useState<string | null>(null)
  const [isNavigating, setIsNavigating] = useState(false)
  const [darkMode, setDarkMode] = useState(false)

  const {
    locations,
    setLocations,
    isLoading,
    error,
    reload,
    reloadNear,
    retry,
    simulateAvailability,
    isRefreshing,
    lastUpdated,
    emptyHint,
    source,
    sourceWarning,
  } = useLocations()
  const {
    recommend,
    isLoading: isRecommendLoading,
    error: recommendError,
    clear: clearRecommend,
  } = useRecommend()

  const [currentLocation, setCurrentLocation] = useState<GeoPoint | null>(null)
  const [isGpsLocating, setIsGpsLocating] = useState(false)
  const [flyToToken, setFlyToToken] = useState(0)
  const [flyToTarget, setFlyToTarget] = useState<GeoPoint | null>(null)
  const [chargingStations, setChargingStations] = useState<ChargingStation[]>([])

  const [destination, setDestination] = useState("")
  const [departureTime, setDepartureTime] = useState("14:30")
  const [batteryPercent, setBatteryPercent] = useState(80)
  const [lowBatteryMode, setLowBatteryMode] = useState(false)
  const [smartSearchActive, setSmartSearchActive] = useState(false)
  const [nearbyStationName, setNearbyStationName] = useState<string | null>(null)
  const [nearbyPlaces, setNearbyPlaces] = useState<NearbyPlace[]>([])
  const [nearbyLoading, setNearbyLoading] = useState(false)
  const [focusedNearbyPlace, setFocusedNearbyPlace] = useState<NearbyPlace | null>(null)
  const [routeSummary, setRouteSummary] = useState<RouteSummary | null>(null)

  useEffect(() => {
    setChargingStations(locationsToChargingStations(locations))
  }, [locations])

  useEffect(() => {
    if (sourceWarning) {
      toast.warning("充電站資料提示", { description: sourceWarning })
    }
  }, [sourceWarning])

  const requestGps = useCallback(() => {
    if (typeof navigator === "undefined" || !navigator.geolocation) {
      toast.error("此瀏覽器不支援 GPS 定位")
      return
    }

    setIsGpsLocating(true)
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const point = { lat: pos.coords.latitude, lng: pos.coords.longitude }
        setCurrentLocation(point)
        setFlyToTarget(point)
        setFlyToToken((t) => t + 1)
        setIsGpsLocating(false)
        void reloadNear(point)
      },
      (err) => {
        setIsGpsLocating(false)
        const description =
          err.code === err.PERMISSION_DENIED
            ? "請在瀏覽器設定中允許此網站使用位置資訊"
            : err.message || "定位逾時或無法取得座標"
        toast.error("無法取得 GPS 定位", { description })
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 10000 }
    )
  }, [reloadNear])

  useEffect(() => {
    requestGps()
  }, [requestGps])

  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add("dark")
    } else {
      document.documentElement.classList.remove("dark")
    }
  }, [darkMode])

  const handleLogin = () => {
    setIsLoggedIn(true)
  }

  const handleLogout = () => {
    setIsLoggedIn(false)
    setSelectedDestination(null)
    setIsNavigating(false)
    setLowBatteryMode(false)
    setSmartSearchActive(false)
    setFlyToTarget(null)
    setCurrentLocation(null)
    setDestination("")
    clearRecommend()
  }

  const handleNavigate = (destination: string) => {
    setSelectedDestination(destination)
    setIsNavigating(false)
  }

  const handleStartNavigation = () => {
    if (!currentLocation) {
      toast.error("請先取得 GPS 定位再開始導航")
      return
    }
    setIsNavigating(true)
  }

  const handleCancelNavigation = () => {
    setSelectedDestination(null)
    setIsNavigating(false)
    setRouteSummary(null)
  }

  const handleNearbyPlacesChange = useCallback(
    (payload: { stationName: string | null; places: NearbyPlace[]; loading: boolean }) => {
      setNearbyStationName(payload.stationName)
      setNearbyPlaces(payload.places)
      setNearbyLoading(payload.loading)
      if (!payload.stationName) setFocusedNearbyPlace(null)
    },
    []
  )

  const handlePlacesSelect = useCallback((place: PlacePick) => {
    setFlyToTarget(place.location)
    setFlyToToken((t) => t + 1)
    toast.message(`已移動至 ${place.name}`, {
      description: "此搜尋只移動地圖，未啟動 AI 規劃",
    })
  }, [])

  const handleSmartRangeSearch = useCallback(async () => {
    if (!currentLocation) {
      toast.error("請先允許瀏覽器 GPS 定位")
      return
    }
    if (!destination.trim()) {
      toast.error("請在智慧續航面板輸入目的地")
      return
    }

    setSmartSearchActive(true)
    const isLow = batteryPercent < LOW_BATTERY_THRESHOLD
    setLowBatteryMode(isLow)

    try {
      const result = await recommend({
        lat: currentLocation.lat,
        lng: currentLocation.lng,
        batteryPercent,
        departureTime,
        destination: destination.trim(),
        isAvailableNow: isLow,
        stations: nearestStationInputs(
          locationsToRankInput(locations),
          currentLocation,
          80
        ).map((station) => ({
          id: station.id,
          name: station.name,
          lat: station.lat,
          lng: station.lng,
          cost: station.cost,
          available: station.available,
          poi_count: station.poiCount,
        })),
      })
      setLocations((prev) => applyRecommendations(prev, result.items))

      const top = result.items[0]
      if (top?.lat != null && top?.lng != null) {
        setFlyToTarget({ lat: top.lat, lng: top.lng })
      } else if (top) {
        const matched = locations.find(
          (loc) =>
            String(loc.id) === String(top.id) ||
            (top.name && loc.name === top.name)
        )
        if (matched?.lat != null && matched.lng != null) {
          setFlyToTarget({ lat: matched.lat, lng: matched.lng })
        }
      }

      setFlyToToken((t) => t + 1)

      if (result.items.length === 0) {
        toast.warning("AI 沒有回傳推薦站點", {
          description: isLow
            ? `已改為篩選高功率快充站 · 電量 ${batteryPercent}%`
            : `出發 ${departureTime} · 剩餘電量 ${batteryPercent}%`,
        })
      } else {
        toast.success(`已找到 ${result.items.length} 個推薦充電站`, {
          description: top?.name
            ? `最佳建議：${top.name}`
            : `出發 ${departureTime} · 剩餘電量 ${batteryPercent}%`,
        })
      }
    } catch (e) {
      const message = e instanceof Error ? e.message : "AI 推薦失敗"
      if (isLow) {
        toast.warning("AI 推薦失敗，已改為篩選快充站", { description: message })
      } else {
        toast.error("無法取得 AI 推薦", { description: message })
      }
      setFlyToTarget(currentLocation)
      setFlyToToken((t) => t + 1)
    }
  }, [
    batteryPercent,
    departureTime,
    destination,
    currentLocation,
    recommend,
    setLocations,
    locations,
  ])

  if (!isLoggedIn) {
    return <LoginScreen onLogin={handleLogin} onRegister={() => {}} />
  }

  if (isLoading) {
    return (
      <div className="h-screen w-full flex flex-col items-center justify-center gap-4 bg-background">
        <Loader2 className="w-10 h-10 text-emerald-600 animate-spin" />
        <p className="text-muted-foreground text-sm">正在從 Supabase 載入充電站…</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="h-screen w-full flex flex-col items-center justify-center gap-4 bg-background p-6">
        <p className="text-destructive font-medium text-center">{error}</p>
        <p className="text-sm text-muted-foreground text-center max-w-md">
          請確認 .env.local 已設定 NEXT_PUBLIC_SUPABASE_URL、NEXT_PUBLIC_SUPABASE_ANON_KEY，
          且資料庫存在 public.stations 資料表（含名稱與經緯度欄位）。
        </p>
        <button
          type="button"
          onClick={() => void retry()}
          className="px-4 py-2 rounded-xl bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-500"
        >
          重試
        </button>
      </div>
    )
  }

  const selectedLocation = selectedDestination
    ? findLocationByName(selectedDestination, locations)
    : undefined
  const routeDestination =
    focusedNearbyPlace != null
      ? { lat: focusedNearbyPlace.lat, lng: focusedNearbyPlace.lng }
      : selectedLocation?.lat != null && selectedLocation.lng != null
        ? { lat: selectedLocation.lat, lng: selectedLocation.lng }
        : null

  return (
    <APIProvider
      apiKey={GOOGLE_MAPS_API_KEY}
      language="zh-TW"
      region="TW"
      libraries={["places", "marker"]}
      onError={(error) => {
        console.error("[Google Maps] API 載入失敗:", error)
      }}
    >
      <div className="h-screen w-full flex overflow-hidden">
        <Toaster position="top-center" richColors closeButton />
        <Sidebar
          locations={locations}
          emptyHint={emptyHint}
          onNavigate={handleNavigate}
          onLogout={handleLogout}
          selectedDestination={selectedDestination}
          isNavigating={isNavigating}
          onStartNavigation={handleStartNavigation}
          onCancelNavigation={handleCancelNavigation}
          darkMode={darkMode}
          onDarkModeChange={setDarkMode}
          destination={destination}
          onDestinationChange={setDestination}
          onPlacesSelect={handlePlacesSelect}
          departureTime={departureTime}
          batteryPercent={batteryPercent}
          onDepartureTimeChange={setDepartureTime}
          onBatteryPercentChange={setBatteryPercent}
          onSmartRangeSearch={handleSmartRangeSearch}
          lowBatteryMode={lowBatteryMode}
          smartSearchActive={smartSearchActive}
          isRecommendLoading={isRecommendLoading}
          recommendError={recommendError}
          nearbyStationName={nearbyStationName}
          nearbyPlaces={nearbyPlaces}
          nearbyLoading={nearbyLoading}
          selectedNearbyPlaceId={focusedNearbyPlace?.id}
          onSelectNearbyPlace={setFocusedNearbyPlace}
          routeSummary={routeSummary}
        />

        <div className="flex-1 relative">
          <MapView
            chargingStations={chargingStations}
            selectedDestination={selectedDestination}
            isNavigating={isNavigating}
            currentLocation={currentLocation}
            onRequestGps={requestGps}
            isGpsLocating={isGpsLocating}
            lowBatteryMode={lowBatteryMode}
            flyToToken={flyToToken}
            flyToTarget={flyToTarget}
            onRefresh={currentLocation ? () => reloadNear(currentLocation) : reload}
            onSimulate={simulateAvailability}
            isRefreshing={isRefreshing}
            lastUpdated={lastUpdated}
            dataSourceLabel={source === "express" ? "Express 充電站" : "Supabase 充電站"}
            isRecommendLoading={isRecommendLoading}
            onNearbyPlacesChange={handleNearbyPlacesChange}
            focusedNearbyPlace={focusedNearbyPlace}
            batteryPercent={batteryPercent}
            routeDestination={routeDestination}
            onRouteChange={setRouteSummary}
          />
        </div>
      </div>
    </APIProvider>
  )
}
