"use client"

import { useState } from "react"
import {
  MapPin,
  ChevronRight,
  Clock,
  Heart,
  Sparkles,
  ArrowLeft,
  User,
  MapIcon,
  Download,
  Navigation,
  Moon,
  Bell,
  Info,
  LogOut,
  Settings,
  Menu,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { cn } from "@/lib/utils"
import {
  type Location,
  type LocationType,
  favoriteLocations,
  quickActions,
  filterLocations,
  findLocationByName,
  formatChargerPrice,
  formatStationSchemaDetails,
  stationSchemaCardProps,
} from "@/lib/locations"
import { SmartRangePanel } from "@/components/smart-range-panel"
import { PlacesSearchBox, type PlacePick } from "@/components/places-search-box"
import { LocationCard } from "@/components/location-card"
import { QuickActionChip } from "@/components/quick-action-chip"
import { StationAvailabilityCard } from "@/components/charger-availability"
import { NearbyPlacesList } from "@/components/nearby-places-layer"
import type { NearbyPlace } from "@/lib/nearby-places"
import { aura } from "@/lib/aura-styles"
import type { RouteSummary } from "@/lib/ai/route-types"

type SidebarView = "main" | "search" | "settings" | "navigation"

interface SidebarProps {
  locations: Location[]
  emptyHint?: string | null
  onNavigate: (destination: string) => void
  onLogout: () => void
  selectedDestination: string | null
  isNavigating: boolean
  onStartNavigation: () => void
  onCancelNavigation: () => void
  darkMode: boolean
  onDarkModeChange: (value: boolean) => void
  departureTime: string
  batteryPercent: number
  onDepartureTimeChange: (value: string) => void
  onBatteryPercentChange: (value: number) => void
  onSmartRangeSearch: () => void
  lowBatteryMode: boolean
  smartSearchActive: boolean
  isRecommendLoading?: boolean
  recommendError?: string | null
  destination: string
  onDestinationChange: (value: string) => void
  onPlacesSelect: (place: PlacePick) => void
  nearbyStationName?: string | null
  nearbyPlaces?: NearbyPlace[]
  nearbyLoading?: boolean
  selectedNearbyPlaceId?: string | null
  onSelectNearbyPlace?: (place: NearbyPlace) => void
  routeSummary?: RouteSummary | null
}

export function Sidebar({
  locations,
  emptyHint,
  onNavigate,
  onLogout,
  selectedDestination,
  isNavigating,
  onStartNavigation,
  onCancelNavigation,
  darkMode,
  onDarkModeChange,
  departureTime,
  batteryPercent,
  onDepartureTimeChange,
  onBatteryPercentChange,
  onSmartRangeSearch,
  lowBatteryMode,
  smartSearchActive,
  isRecommendLoading = false,
  recommendError = null,
  destination,
  onDestinationChange,
  onPlacesSelect,
  nearbyStationName = null,
  nearbyPlaces = [],
  nearbyLoading = false,
  selectedNearbyPlaceId = null,
  onSelectNearbyPlace,
  routeSummary = null,
}: SidebarProps) {
  const [view, setView] = useState<SidebarView>("main")
  const [searchQuery, setSearchQuery] = useState("")
  const [activeFilter, setActiveFilter] = useState<LocationType | null>(null)
  const [trafficAlerts, setTrafficAlerts] = useState(true)
  const [isCollapsed, setIsCollapsed] = useState(false)

  const effectiveFilter: LocationType | null =
    lowBatteryMode ? "ev-charger" : activeFilter

  const hasAiRecommend = locations.some((item) => item.isRecommended)

  const filteredLocations = filterLocations(
    locations,
    effectiveFilter,
    view === "search" ? searchQuery : undefined
  ).filter((item) => {
    if (hasAiRecommend) return true
    if (!lowBatteryMode) return true
    if (item.type !== "ev-charger") return false
    return item.chargerType === "DC"
  })

  const recommendedLocations = filteredLocations
    .filter((item) => item.isRecommended)
    .sort((a, b) => (a.recommendRank ?? 99) - (b.recommendRank ?? 99))

  const listLocations = hasAiRecommend
    ? [
        ...recommendedLocations,
        ...filteredLocations.filter((item) => !item.isRecommended),
      ]
    : filteredLocations

  const handleQuickAction = (filterType: LocationType) => {
    setActiveFilter((prev) => (prev === filterType ? null : filterType))
  }

  const handleSelectLocation = (location: string) => {
    onNavigate(location)
    setView("navigation")
  }

  const selectedLocation = selectedDestination
    ? findLocationByName(selectedDestination, locations)
    : undefined

  // Collapsed sidebar
  if (isCollapsed) {
    return (
      <div
        className={cn(
          "w-16 h-full flex flex-col items-center py-4 gap-4",
          aura.glassShell
        )}
      >
        <button
          onClick={() => setIsCollapsed(false)}
          className={cn("w-10 h-10 rounded-full flex items-center justify-center", aura.btnGhost)}
        >
          <Menu className="w-5 h-5" />
        </button>
        <div className="w-10 h-10 rounded-full bg-emerald-500/20 ring-1 ring-emerald-500/30 flex items-center justify-center shadow-inner">
          <MapPin className="w-5 h-5 text-emerald-600" />
        </div>
        <div className="flex-1" />
        <button
          onClick={() => {
            setIsCollapsed(false)
            setView("settings")
          }}
          className={cn("w-10 h-10 rounded-full flex items-center justify-center", aura.btnGhost)}
        >
          <Settings className="w-5 h-5" />
        </button>
        <Avatar className="w-10 h-10 border-2 border-primary cursor-pointer">
          <AvatarImage src="/placeholder.svg" alt="使用者頭像" />
          <AvatarFallback className="bg-primary text-primary-foreground text-sm">ME</AvatarFallback>
        </Avatar>
      </div>
    )
  }

  return (
    <div className={cn("w-96 h-full flex flex-col z-20", aura.glassShell)}>
      {/* Header */}
      <div className="p-4 border-b border-white/30 dark:border-white/10">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setIsCollapsed(true)}
              className={cn("w-10 h-10 rounded-full flex items-center justify-center", aura.btnGhost)}
            >
              <Menu className="w-5 h-5" />
            </button>
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-emerald-500 to-emerald-700 flex items-center justify-center shadow-md shadow-emerald-600/20">
                <MapPin className="w-4 h-4 text-white" />
              </div>
              <span className="font-bold text-foreground text-lg tracking-tight">MapExplore</span>
            </div>
          </div>
          <Avatar className="w-10 h-10 border-2 border-primary cursor-pointer">
            <AvatarImage src="/placeholder.svg" alt="使用者頭像" />
            <AvatarFallback className="bg-primary text-primary-foreground text-sm">ME</AvatarFallback>
          </Avatar>
        </div>

        <PlacesSearchBox
          placeholder="搜尋地點（僅移動地圖）"
          onPlaceSelect={(place) => {
            onPlacesSelect(place)
            setView("main")
          }}
        />
        <p className="text-[10px] text-muted-foreground mt-1.5 px-1">
          上方為 Google 地點搜尋，不會啟動 AI 規劃
        </p>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {view === "main" && (
          <div className="p-4 space-y-6">
            {/* Quick Actions */}
            <div className="flex flex-wrap gap-2">
              {quickActions.map((action) => (
                <QuickActionChip
                  key={action.label}
                  icon={action.icon}
                  label={action.label}
                  selected={effectiveFilter === action.filterType}
                  onClick={() => handleQuickAction(action.filterType)}
                />
              ))}
            </div>

            <SmartRangePanel
              destination={destination}
              departureTime={departureTime}
              batteryPercent={batteryPercent}
              onDestinationChange={onDestinationChange}
              onDepartureTimeChange={onDepartureTimeChange}
              onBatteryPercentChange={onBatteryPercentChange}
              onSearch={onSmartRangeSearch}
              isLoading={isRecommendLoading}
              error={recommendError}
              compact
            />

            {/* Recent Searches */}
            <div>
              <div className="flex items-center gap-2 mb-3">
                <Clock className="w-4 h-4 text-emerald-600" />
                <span className={aura.sectionTitle}>
                  {recommendedLocations.length > 0
                    ? "AI 推薦充電站"
                    : lowBatteryMode
                      ? "優先快充站 (DC)"
                      : activeFilter === "ev-charger"
                        ? "充電樁"
                        : "最近搜尋"}
                </span>
              </div>
              <div className="space-y-3">
                {filteredLocations.length === 0 ? (
                  <p className="text-sm text-muted-foreground px-1 py-4 text-center">
                    {emptyHint ?? "暫無充電站"}
                  </p>
                ) : (
                  listLocations.map((item) => (
                    <LocationCard
                      key={item.id}
                      name={item.name}
                      address={item.address}
                      price={item.price}
                      chargerType={item.chargerType}
                      availableSlots={item.availableSlots}
                      totalChargers={item.totalChargers}
                      availableChargers={item.availableChargers}
                      stationStatus={item.stationStatus}
                      portAvailability={item.portAvailability}
                      {...stationSchemaCardProps(item)}
                      lowBatteryHighlight={lowBatteryMode && !item.isRecommended}
                      isRecommended={item.isRecommended}
                      recommendRank={item.recommendRank}
                      recommendReason={item.recommendReason}
                      onClick={() => handleSelectLocation(item.name)}
                    />
                  ))
                )}
              </div>
            </div>

            {(nearbyLoading || nearbyPlaces.length > 0 || nearbyStationName) && onSelectNearbyPlace && (
              <div className={cn("rounded-2xl p-3 shadow-lg", aura.glassCard)}>
                <NearbyPlacesList
                  stationName={nearbyStationName}
                  places={nearbyPlaces}
                  loading={nearbyLoading}
                  selectedPlaceId={selectedNearbyPlaceId}
                  onSelect={onSelectNearbyPlace}
                />
              </div>
            )}

            {/* Favorite Locations */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <Heart className="w-4 h-4 text-emerald-600" />
                  <span className={aura.sectionTitle}>喜愛地點</span>
                </div>
                <button
                  type="button"
                  className="text-sm text-emerald-600 font-medium hover:underline transition-all duration-300"
                >
                  管理
                </button>
              </div>
              <div className="space-y-3">
                {favoriteLocations
                  .filter((item) => !activeFilter || item.type === activeFilter)
                  .map((item) => (
                    <LocationCard
                      key={item.id}
                      name={item.name}
                      address={item.address}
                      icon={item.icon}
                      onClick={() => handleSelectLocation(item.name)}
                    />
                  ))}
              </div>
            </div>

            {/* Explore Banner */}
            <div className="relative rounded-2xl overflow-hidden h-40 shadow-xl border border-white/30 dark:border-white/10">
              <div className="absolute inset-0 bg-gradient-to-br from-primary/80 to-primary/40" />
              <div
                className="absolute inset-0"
                style={{
                  backgroundImage: `url('https://images.unsplash.com/photo-1519608425089-7f3bfa6f6bb8?w=800&q=80')`,
                  backgroundSize: "cover",
                  backgroundPosition: "center",
                  opacity: 0.5,
                }}
              />
              <div className="absolute inset-0 flex flex-col justify-end p-4">
                <div className="flex items-center gap-2 text-foreground mb-1">
                  <Sparkles className="w-4 h-4" />
                  <span className="text-sm font-medium">探索周邊</span>
                </div>
                <p className="text-foreground/80 text-sm mb-3">發現您喜愛的新去處</p>
                <Button size="sm" className={cn("w-fit rounded-full", aura.btnPrimary)}>
                  開始探索
                </Button>
              </div>
            </div>
          </div>
        )}

        {view === "search" && (
          <div className="p-4 space-y-4">
            <div className="flex items-center gap-3">
              <button
                onClick={() => setView("main")}
                className={cn("w-10 h-10 rounded-full flex items-center justify-center shrink-0", aura.btnGhost)}
              >
                <ArrowLeft className="w-5 h-5" />
              </button>
              <PlacesSearchBox
                placeholder="搜尋地點（僅移動地圖）"
                autoFocus
                onPlaceSelect={onPlacesSelect}
              />
            </div>

            <SmartRangePanel
              destination={destination}
              departureTime={departureTime}
              batteryPercent={batteryPercent}
              onDestinationChange={onDestinationChange}
              onDepartureTimeChange={onDepartureTimeChange}
              onBatteryPercentChange={onBatteryPercentChange}
              onSearch={onSmartRangeSearch}
              isLoading={isRecommendLoading}
              error={recommendError}
              compact
            />

            {smartSearchActive && recommendedLocations.length > 0 && (
              <p className="rounded-xl bg-violet-500/10 border border-violet-400/30 text-violet-700 dark:text-violet-300 px-3 py-2 text-xs font-medium">
                已依目前位置與電量標出 {recommendedLocations.length} 個 AI 推薦站
              </p>
            )}

            {smartSearchActive && lowBatteryMode && recommendedLocations.length === 0 && (
              <p className={aura.alertLowBattery}>電量較低，已優先為您篩選高功率快充站！</p>
            )}

            <div className="flex flex-wrap gap-2">
              {quickActions.map((action) => (
                <QuickActionChip
                  key={action.label}
                  icon={action.icon}
                  label={action.label}
                  selected={effectiveFilter === action.filterType}
                  onClick={() => handleQuickAction(action.filterType)}
                />
              ))}
            </div>

            <div className="space-y-3">
              {filteredLocations.length === 0 ? (
                <p className="text-sm text-muted-foreground px-1 py-4 text-center">
                  {emptyHint ?? "暫無充電站"}
                </p>
              ) : (
                listLocations.map((item) => (
                  <LocationCard
                    key={item.id}
                    name={item.name}
                    address={item.address}
                    price={item.price}
                    chargerType={item.chargerType}
                    availableSlots={item.availableSlots}
                    totalChargers={item.totalChargers}
                    availableChargers={item.availableChargers}
                    stationStatus={item.stationStatus}
                    portAvailability={item.portAvailability}
                    {...stationSchemaCardProps(item)}
                    lowBatteryHighlight={lowBatteryMode && !item.isRecommended}
                    isRecommended={item.isRecommended}
                    recommendRank={item.recommendRank}
                    recommendReason={item.recommendReason}
                    onClick={() => handleSelectLocation(item.name)}
                  />
                ))
              )}
            </div>
          </div>
        )}

        {view === "settings" && (
          <div className="p-4 space-y-4">
            <div className="flex items-center gap-3 mb-2">
              <button
                onClick={() => setView("main")}
                className={cn("w-10 h-10 rounded-full flex items-center justify-center", aura.btnGhost)}
              >
                <ArrowLeft className="w-5 h-5" />
              </button>
              <h2 className="text-lg font-bold text-foreground tracking-tight">設定</h2>
            </div>

            {/* Menu Items */}
            <div className="space-y-2">
              {[
                { icon: User, label: "個人資料", description: "管理您的帳戶與隱私設定" },
                { icon: MapIcon, label: "地圖設定" },
                { icon: Download, label: "離線地圖", description: "3 個已下載" },
                { icon: Navigation, label: "導航設定" },
              ].map((item) => (
                <button
                  key={item.label}
                  type="button"
                  className={cn("w-full flex items-center gap-3 p-4 rounded-2xl text-left", aura.glassCardInteractive)}
                >
                  <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center shrink-0">
                    <item.icon className="w-5 h-5 text-foreground" />
                  </div>
                  <div className="flex-1 text-left">
                    <p className="font-medium text-foreground">{item.label}</p>
                    {item.description && <p className="text-sm text-primary">{item.description}</p>}
                  </div>
                  <ChevronRight className="w-5 h-5 text-muted-foreground" />
                </button>
              ))}
            </div>

            {/* Toggle Settings */}
            <div className="space-y-2">
              <div className={cn("flex items-center justify-between p-4 rounded-2xl", aura.glassCard)}>
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-emerald-500/15 flex items-center justify-center">
                    <Moon className="w-5 h-5 text-emerald-600" />
                  </div>
                  <span className="font-semibold text-foreground">深色模式</span>
                </div>
                <Switch checked={darkMode} onCheckedChange={onDarkModeChange} />
              </div>

              <div className={cn("flex items-center justify-between p-4 rounded-2xl", aura.glassCard)}>
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center">
                    <Bell className="w-5 h-5 text-foreground" />
                  </div>
                  <span className="font-medium text-foreground">即時交通提醒</span>
                </div>
                <Switch checked={trafficAlerts} onCheckedChange={setTrafficAlerts} />
              </div>
            </div>

            {/* About */}
            <button
              type="button"
              className={cn("w-full flex items-center gap-3 p-4 rounded-2xl text-left", aura.glassCardInteractive)}
            >
              <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center">
                <Info className="w-5 h-5 text-foreground" />
              </div>
              <div className="flex-1 text-left">
                <p className="font-medium text-foreground">關於</p>
                <p className="text-sm text-muted-foreground">v 2.4.1 (Build 882)</p>
              </div>
              <ChevronRight className="w-5 h-5 text-muted-foreground" />
            </button>

            {/* Logout */}
            <button
              type="button"
              onClick={onLogout}
              className="w-full flex items-center justify-center gap-2 p-4 rounded-2xl text-destructive bg-destructive/5 backdrop-blur-md border border-destructive/20 shadow-sm hover:bg-destructive/10 hover:shadow-md active:scale-[0.99] transition-all duration-300"
            >
              <LogOut className="w-5 h-5" />
              <span className="font-medium">登出帳號</span>
            </button>
          </div>
        )}

        {view === "navigation" && selectedDestination && (
          <div className="p-4 space-y-4">
            <div className="flex items-center gap-3 mb-2">
              <button
                onClick={() => {
                  setView("main")
                  onCancelNavigation()
                }}
                className={cn("w-10 h-10 rounded-full flex items-center justify-center", aura.btnGhost)}
              >
                <ArrowLeft className="w-5 h-5" />
              </button>
              <h2 className="text-lg font-bold text-foreground tracking-tight truncate">
                導航至 {selectedDestination}
              </h2>
            </div>

            {/* Route Info */}
            <div className={cn("rounded-2xl p-4 space-y-4 shadow-lg", aura.glassCard)}>
              <div className="flex items-center gap-4">
                <div className="w-3 h-3 rounded-full bg-primary" />
                <div className="flex-1">
                  <p className="text-sm text-muted-foreground">起點</p>
                  <p className="font-medium text-foreground">目前位置</p>
                </div>
              </div>
              <div className="ml-1.5 w-0.5 h-8 bg-primary/50" />
              <div className="flex items-center gap-4">
                <div className="w-3 h-3 rounded-full bg-destructive" />
                <div className="flex-1">
                  <p className="text-sm text-muted-foreground">終點</p>
                  <p className="font-medium text-foreground">{selectedDestination}</p>
                  {selectedLocation?.address && (
                    <p className="text-sm text-muted-foreground mt-1">{selectedLocation.address}</p>
                  )}
                  {selectedLocation &&
                    formatStationSchemaDetails(selectedLocation).map((line) => (
                      <p key={line} className="text-xs text-muted-foreground mt-0.5">
                        {line}
                      </p>
                    ))}
                  {selectedLocation?.price !== undefined && (
                    <p className="text-sm text-primary mt-1">
                      {formatChargerPrice(selectedLocation.price)}
                    </p>
                  )}
                </div>
              </div>
            </div>

            {selectedLocation?.type === "ev-charger" &&
              selectedLocation.availableChargers !== undefined &&
              selectedLocation.totalChargers !== undefined && (
                <StationAvailabilityCard
                  available={selectedLocation.availableChargers}
                  total={selectedLocation.totalChargers}
                  status={selectedLocation.stationStatus}
                  ports={selectedLocation.portAvailability}
                />
              )}

            {(nearbyLoading || nearbyPlaces.length > 0) && onSelectNearbyPlace && (
              <div className={cn("rounded-2xl p-3 shadow-lg", aura.glassCard)}>
                <NearbyPlacesList
                  stationName={nearbyStationName ?? selectedDestination}
                  places={nearbyPlaces}
                  loading={nearbyLoading}
                  selectedPlaceId={selectedNearbyPlaceId}
                  onSelect={onSelectNearbyPlace}
                />
              </div>
            )}

            {/* Time & Distance */}
            <div className="grid grid-cols-2 gap-4">
              <div className={cn("rounded-xl p-4 text-center shadow-md", aura.glassCard)}>
                <p className="text-xs font-medium text-muted-foreground mb-1 uppercase tracking-wide">預估時間</p>
                <div className="flex items-baseline justify-center gap-1">
                  <span className="text-2xl font-bold text-foreground">
                    {routeSummary?.durationText ?? "計算中"}
                  </span>
                </div>
                <p className="text-xs text-primary mt-1">
                  {isNavigating ? "導航中" : "AI 路線預覽"}
                </p>
              </div>
              <div className={cn("rounded-xl p-4 text-center shadow-md", aura.glassCard)}>
                <p className="text-xs font-medium text-muted-foreground mb-1 uppercase tracking-wide">距離</p>
                <div className="flex items-baseline justify-center gap-1">
                  <span className="text-2xl font-bold text-foreground">
                    {routeSummary?.distanceText ?? "計算中"}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  {routeSummary?.summary ? `經由 ${routeSummary.summary}` : "Google Directions"}
                </p>
              </div>
            </div>

            {routeSummary && (
              <div className="space-y-2">
                <p className="text-sm font-medium text-muted-foreground">建議路線</p>
                <div
                  className="w-full flex items-center gap-3 p-3 rounded-xl text-left bg-emerald-500/15 border-2 border-emerald-500/50 shadow-md"
                >
                  <div className="flex-1">
                    <p className="font-medium text-foreground">AI 最佳駕車路線</p>
                    <p className="text-sm text-muted-foreground">
                      {routeSummary.durationText} · {routeSummary.distanceText}
                    </p>
                  </div>
                  <span className="text-xs text-primary">考量路況</span>
                </div>
              </div>
            )}

            {/* Start Navigation Button */}
            <Button
              onClick={onStartNavigation}
              className={cn("w-full h-14 rounded-2xl font-bold text-lg", aura.btnPrimary)}
            >
              <Navigation className="w-5 h-5 mr-2" />
              開始導航
            </Button>
          </div>
        )}
      </div>

      {/* Footer Navigation */}
      <div className="p-4 border-t border-white/30 dark:border-white/10 bg-white/40 dark:bg-zinc-950/40 backdrop-blur-md">
        <div className="flex justify-around">
          {[
            { icon: MapPin, label: "探索", view: "main" as SidebarView },
            { icon: Clock, label: "近期", view: "search" as SidebarView },
            { icon: Navigation, label: "導航", view: "navigation" as SidebarView },
            { icon: Settings, label: "設定", view: "settings" as SidebarView },
          ].map((item) => (
            <button
              key={item.label}
              type="button"
              onClick={() => setView(item.view)}
              className={cn(
                "flex flex-col items-center gap-1 p-2.5 rounded-xl transition-all duration-300",
                view === item.view
                  ? "text-emerald-600 bg-emerald-500/15 scale-105 shadow-sm ring-1 ring-emerald-500/30"
                  : "text-muted-foreground hover:text-foreground hover:bg-white/50 dark:hover:bg-white/5 active:scale-95"
              )}
            >
              <item.icon className="w-5 h-5" />
              <span className="text-xs">{item.label}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
