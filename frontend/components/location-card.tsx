"use client"

import type { LucideIcon } from "lucide-react"
import { MapPin, ChevronRight, Zap, Gauge, CircleDollarSign, Sparkles } from "lucide-react"
import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { formatChargerPrice, formatStationSchemaDetails } from "@/lib/locations"
import type { ChargerPowerType } from "@/lib/locations"
import {
  AVAILABILITY_THEME,
  getAvailabilityLight,
  type ConnectorAvailability,
  type StationStatus,
} from "@/lib/charger-availability"
import { AvailabilityCountLabel } from "@/components/charger-availability"

export interface LocationCardProps {
  name: string
  address: string
  onClick: () => void
  icon?: LucideIcon
  price?: number
  chargerType?: ChargerPowerType
  availableSlots?: number
  totalChargers?: number
  availableChargers?: number
  stationStatus?: StationStatus
  portAvailability?: ConnectorAvailability[]
  plugType?: string
  portType?: string
  city?: string
  service_time?: string
  charging_rate?: string
  parking_rate?: string
  spaces?: number
  charging_points?: number
  lowBatteryHighlight?: boolean
  isRecommended?: boolean
  recommendRank?: number
  recommendReason?: string
  className?: string
}

export function LocationCard({
  name,
  address,
  onClick,
  icon: Icon = MapPin,
  price,
  chargerType,
  availableSlots,
  totalChargers,
  availableChargers,
  stationStatus,
  plugType,
  portType,
  city,
  service_time,
  charging_rate,
  parking_rate,
  spaces,
  charging_points,
  lowBatteryHighlight = false,
  isRecommended = false,
  recommendRank,
  recommendReason,
  className,
}: LocationCardProps) {
  const schemaDetails = formatStationSchemaDetails({
    city,
    address,
    service_time,
    charging_rate,
    parking_rate,
    spaces,
    charging_points,
  })
  const isEv = price !== undefined || chargerType !== undefined || Boolean(plugType || portType || charging_points != null)
  const showDcPriority = lowBatteryHighlight && chargerType === "DC"
  const isAc = chargerType === "AC"
  const available = availableChargers ?? availableSlots
  const total = totalChargers
  const showAvailability = isEv && available !== undefined && total !== undefined
  const light = showAvailability
    ? getAvailabilityLight(available ?? 0, total ?? 0, stationStatus)
    : "green"
  const theme = AVAILABILITY_THEME[light]

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "group w-full flex gap-3.5 p-4 rounded-2xl text-left",
        "bg-white/80 dark:bg-zinc-900/65 backdrop-blur-md",
        "border shadow-md hover:shadow-xl",
        "hover:-translate-y-0.5 active:scale-[0.99]",
        "transition-all duration-300",
        showDcPriority
          ? "border-destructive/40 ring-1 ring-destructive/25 hover:border-destructive/60"
          : isRecommended
            ? "border-violet-400/60 ring-1 ring-violet-400/30 hover:border-violet-400"
            : "border-white/50 dark:border-white/10 hover:border-emerald-300/50 dark:hover:border-emerald-500/30",
        className
      )}
    >
      <div
        className={cn(
          "w-12 h-12 rounded-2xl flex items-center justify-center shrink-0 shadow-inner transition-transform duration-300 group-hover:scale-105",
          showAvailability
            ? cn("text-white", theme.pin)
            : showDcPriority
              ? "bg-gradient-to-br from-red-500 to-red-600 text-white"
              : isEv
                ? "bg-gradient-to-br from-emerald-500 to-emerald-700 text-white"
                : "bg-gradient-to-br from-emerald-600/90 to-emerald-800 text-white"
        )}
      >
        {showAvailability ? (
          <span className="text-lg font-black tabular-nums leading-none">
            {stationStatus === "offline" || stationStatus === "maintenance" || (total ?? 0) <= 0
              ? "—"
              : available}
          </span>
        ) : (
          <Icon className="w-6 h-6" />
        )}
      </div>

      <div className="flex-1 min-w-0 flex flex-col gap-2">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <h3 className="text-base font-bold text-foreground leading-snug truncate pr-1">
              {name || "未命名充電站"}
            </h3>
            <p className="text-sm text-muted-foreground mt-0.5 line-clamp-2 leading-relaxed">
              {address || "—"}
            </p>
            {schemaDetails.length > 0 && (
              <p className="text-[11px] text-muted-foreground/80 mt-1 line-clamp-2 leading-relaxed">
                {schemaDetails.join(" · ")}
              </p>
            )}
          </div>
          <ChevronRight className="w-5 h-5 text-muted-foreground/60 shrink-0 mt-0.5 transition-transform duration-300 group-hover:translate-x-0.5 group-hover:text-emerald-600" />
        </div>

        {isEv && (
          <div className="flex flex-wrap gap-1.5">
            {chargerType && (
              <Badge
                className={cn(
                  "rounded-lg px-2 py-1 text-[11px] font-semibold border-0 shadow-sm",
                  chargerType === "DC"
                    ? showDcPriority
                      ? "bg-red-500/15 text-red-700 dark:text-red-300 ring-1 ring-red-500/30"
                      : "bg-amber-500/15 text-amber-800 dark:text-amber-200"
                    : "bg-slate-500/15 text-slate-700 dark:text-slate-300"
                )}
              >
                <Zap className="w-3 h-3" />
                {chargerType === "DC" ? "DC 快充" : "AC 慢充"}
              </Badge>
            )}
            {price !== undefined && (
              <Badge className="rounded-lg px-2 py-1 text-[11px] font-semibold border-0 bg-emerald-500/15 text-emerald-800 dark:text-emerald-200 shadow-sm">
                <CircleDollarSign className="w-3 h-3" />
                {formatChargerPrice(price)}
              </Badge>
            )}
            {showAvailability && (
              <AvailabilityCountLabel
                available={available ?? 0}
                total={total ?? 0}
                status={stationStatus}
              />
            )}
            {isRecommended && (
              <Badge className="rounded-lg px-2 py-1 text-[11px] font-bold border-0 bg-violet-500 text-white shadow-sm">
                <Sparkles className="w-3 h-3" />
                {recommendRank ? `AI 推薦 #${recommendRank}` : "AI 推薦"}
              </Badge>
            )}
            {showDcPriority && (
              <Badge className="rounded-lg px-2 py-1 text-[11px] font-bold border-0 bg-destructive text-destructive-foreground shadow-sm animate-pulse">
                <Gauge className="w-3 h-3" />
                優先推薦
              </Badge>
            )}
            {isAc && lowBatteryHighlight && (
              <Badge variant="outline" className="rounded-lg text-[10px] opacity-60 line-through">
                慢充
              </Badge>
            )}
          </div>
        )}

        {isRecommended && recommendReason && (
          <p className="text-xs text-violet-700 dark:text-violet-300 leading-relaxed">
            {recommendReason}
          </p>
        )}
      </div>
    </button>
  )
}
