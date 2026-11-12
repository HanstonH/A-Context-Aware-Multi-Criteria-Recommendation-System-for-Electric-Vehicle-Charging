"use client"

import { useState } from "react"
import { ArrowLeft, X, Sparkles } from "lucide-react"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Toaster, toast } from "sonner"
import {
  type LocationType,
  staticDemoLocations,
  favoriteLocations,
  quickActions,
  filterLocations,
  stationSchemaCardProps,
} from "@/lib/locations"
import { SmartRangePanel } from "@/components/smart-range-panel"
import { LocationCard } from "@/components/location-card"
import { QuickActionChip } from "@/components/quick-action-chip"
import { LOW_BATTERY_THRESHOLD } from "@/lib/charging-stations"
import { aura } from "@/lib/aura-styles"
import { cn } from "@/lib/utils"

interface SearchScreenProps {
  onBack: () => void
  onSelectLocation: (location: string) => void
  departureTime?: string
  batteryPercent?: number
  onDepartureTimeChange?: (value: string) => void
  onBatteryPercentChange?: (value: number) => void
  onSmartRangeSearch?: () => void
  lowBatteryMode?: boolean
  smartSearchActive?: boolean
}

export function SearchScreen({
  onBack,
  onSelectLocation,
  departureTime: controlledDeparture,
  batteryPercent: controlledBattery,
  onDepartureTimeChange,
  onBatteryPercentChange,
  onSmartRangeSearch,
  lowBatteryMode: controlledLowBattery,
  smartSearchActive: controlledSmartActive,
}: SearchScreenProps) {
  const [searchQuery, setSearchQuery] = useState("")
  const [destination, setDestination] = useState("")
  const [activeFilter, setActiveFilter] = useState<LocationType | null>(null)

  const [localDeparture, setLocalDeparture] = useState("14:30")
  const [localBattery, setLocalBattery] = useState(80)
  const [localLowBattery, setLocalLowBattery] = useState(false)
  const [localSmartActive, setLocalSmartActive] = useState(false)

  const departureTime = controlledDeparture ?? localDeparture
  const batteryPercent = controlledBattery ?? localBattery
  const lowBatteryMode = controlledLowBattery ?? localLowBattery
  const smartSearchActive = controlledSmartActive ?? localSmartActive

  const setDepartureTime = onDepartureTimeChange ?? setLocalDeparture
  const setBatteryPercent = onBatteryPercentChange ?? setLocalBattery

  const effectiveFilter: LocationType | null = lowBatteryMode ? "ev-charger" : activeFilter

  const filteredLocations = filterLocations(staticDemoLocations, effectiveFilter, searchQuery).filter(
    (item) => {
      if (!lowBatteryMode) return true
      if (item.type !== "ev-charger") return false
      return item.chargerType === "DC"
    }
  )

  const filteredFavorites = favoriteLocations.filter(
    (item) => !effectiveFilter || item.type === effectiveFilter
  )

  const handleSmartSearch = () => {
    const isLow = batteryPercent < LOW_BATTERY_THRESHOLD
    if (onSmartRangeSearch) {
      onSmartRangeSearch()
    } else {
      setLocalLowBattery(isLow)
      setLocalSmartActive(true)
      if (isLow) {
        toast.warning("電量較低，已優先為您篩選高功率快充站！", {
          description: `出發 ${departureTime} · 剩餘電量 ${batteryPercent}%`,
          duration: 5000,
        })
      } else {
        toast.success("續航規劃已更新", {
          description: `出發 ${departureTime} · 剩餘電量 ${batteryPercent}%`,
        })
      }
    }
  }

  return (
    <div className="h-full flex flex-col bg-background/95 backdrop-blur-sm">
      <Toaster position="top-center" richColors closeButton />

      <div
        className={cn(
          "p-4 space-y-4 border-b border-white/30 dark:border-white/10",
          "bg-white/70 dark:bg-zinc-950/70 backdrop-blur-xl shadow-lg"
        )}
      >
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onBack}
            className={cn("w-10 h-10 rounded-full flex items-center justify-center shrink-0", aura.btnGhost)}
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div className="flex-1 relative">
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="搜尋地點..."
              className={cn(aura.glassInset, "h-11 rounded-xl pl-4 pr-10")}
              autoFocus
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery("")}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors duration-300"
              >
                <X className="w-5 h-5" />
              </button>
            )}
          </div>
        </div>

        <SmartRangePanel
          destination={destination}
          departureTime={departureTime}
          batteryPercent={batteryPercent}
          onDestinationChange={setDestination}
          onDepartureTimeChange={setDepartureTime}
          onBatteryPercentChange={setBatteryPercent}
          onSearch={handleSmartSearch}
          compact
        />

        {smartSearchActive && lowBatteryMode && (
          <p className={aura.alertLowBattery}>電量較低，已優先為您篩選高功率快充站！</p>
        )}

        <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-hide">
          {quickActions.map((action) => (
            <QuickActionChip
              key={action.label}
              icon={action.icon}
              label={action.label}
              selected={effectiveFilter === action.filterType}
              onClick={() =>
                setActiveFilter((prev) =>
                  prev === action.filterType ? null : action.filterType
                )
              }
            />
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        <section>
          <div className="flex justify-between items-center mb-3">
            <h2 className={aura.sectionTitle}>
              {lowBatteryMode ? "優先快充站 (DC)" : activeFilter === "ev-charger" ? "充電樁" : "最近搜尋"}
            </h2>
            <button type="button" className="text-sm text-emerald-600 font-medium hover:underline transition-all duration-300">
              清除全部
            </button>
          </div>
          <div className="space-y-3">
            {filteredLocations.length === 0 ? (
              <p className="text-sm text-muted-foreground py-8 text-center">沒有符合條件的地點</p>
            ) : (
              filteredLocations.map((item) => (
                <LocationCard
                  key={item.id}
                  name={item.name}
                  address={item.address}
                  price={item.price}
                  chargerType={item.chargerType}
                  availableSlots={item.availableSlots}
                  lowBatteryHighlight={lowBatteryMode}
                  {...stationSchemaCardProps(item)}
                  onClick={() => onSelectLocation(item.name)}
                />
              ))
            )}
          </div>
        </section>

        <section>
          <div className="flex justify-between items-center mb-3">
            <h2 className={aura.sectionTitle}>喜愛地點</h2>
            <button type="button" className="text-sm text-emerald-600 font-medium hover:underline transition-all duration-300">
              管理
            </button>
          </div>
          <div className="space-y-3">
            {filteredFavorites.map((item) => (
              <LocationCard
                key={item.id}
                name={item.name}
                address={item.address}
                icon={item.icon}
                onClick={() => onSelectLocation(item.name)}
              />
            ))}
          </div>
        </section>

        <div className="relative rounded-2xl overflow-hidden h-40 shadow-xl border border-white/30 dark:border-white/10">
          <div className="absolute inset-0 bg-gradient-to-br from-emerald-600/80 to-emerald-800/60" />
          <div
            className="absolute inset-0"
            style={{
              backgroundImage: `url('https://images.unsplash.com/photo-1519608425089-7f3bfa6f6bb8?w=800&q=80')`,
              backgroundSize: "cover",
              backgroundPosition: "center",
              opacity: 0.45,
            }}
          />
          <div className="absolute inset-0 flex flex-col justify-end p-4 backdrop-blur-[2px]">
            <div className="flex items-center gap-2 text-white mb-1">
              <Sparkles className="w-4 h-4" />
              <span className="text-sm font-bold">探索周邊</span>
            </div>
            <p className="text-white/90 text-sm mb-3">發現您喜愛的新去處</p>
            <Button size="sm" className={cn("w-fit rounded-full", aura.btnPrimary)}>
              開始探索
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
