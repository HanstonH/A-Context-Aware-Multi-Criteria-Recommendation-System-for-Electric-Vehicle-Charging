"use client"

import { Clock, Battery, Route, Sparkles, AlertTriangle, Loader2, MapPin } from "lucide-react"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Slider } from "@/components/ui/slider"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { aura } from "@/lib/aura-styles"

export interface SmartRangeFormValues {
  destination: string
  departureTime: string
  batteryPercent: number
}

interface SmartRangePanelProps {
  destination: string
  departureTime: string
  batteryPercent: number
  onDestinationChange: (value: string) => void
  onDepartureTimeChange: (value: string) => void
  onBatteryPercentChange: (value: number) => void
  onSearch: () => void
  className?: string
  compact?: boolean
  isLoading?: boolean
  error?: string | null
}

export function SmartRangePanel({
  destination,
  departureTime,
  batteryPercent,
  onDestinationChange,
  onDepartureTimeChange,
  onBatteryPercentChange,
  onSearch,
  className,
  compact = false,
  isLoading = false,
  error = null,
}: SmartRangePanelProps) {
  const isLowBattery = batteryPercent < 20

  return (
    <div
      className={cn(
        aura.glassCard,
        "rounded-2xl p-4 shadow-lg space-y-4 relative overflow-hidden",
        className
      )}
    >
      <div
        className="absolute inset-0 bg-gradient-to-br from-emerald-500/8 via-transparent to-transparent pointer-events-none"
        aria-hidden
      />

      <div className="flex items-start gap-3 relative">
        <div className="w-11 h-11 rounded-2xl bg-gradient-to-br from-emerald-500 to-emerald-700 flex items-center justify-center shrink-0 shadow-lg shadow-emerald-600/25">
          <Route className="w-5 h-5 text-white" />
        </div>
        <div className="min-w-0">
          <h3 className="font-bold text-foreground text-sm tracking-tight">智慧續航搜尋</h3>
          <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed">
            輸入目的地，並結合出發時間與剩餘電量，交給 AI 規劃充電站
          </p>
        </div>
      </div>

      <div className={cn("gap-4 relative", compact ? "space-y-3" : "grid sm:grid-cols-2")}>
        <div className={cn("space-y-2", !compact && "sm:col-span-2")}>
          <Label
            htmlFor="smart-destination"
            className="text-xs font-medium text-muted-foreground flex items-center gap-1.5"
          >
            <MapPin className="w-3.5 h-3.5 text-emerald-600" />
            目的地（智慧續航）
          </Label>
          <Input
            id="smart-destination"
            type="text"
            value={destination}
            onChange={(e) => onDestinationChange(e.target.value)}
            placeholder="例如：台北車站、高雄夢時代…"
            className={cn(aura.glassInset, "h-10 rounded-xl border-white/50")}
          />
        </div>

        <div className="space-y-2">
          <Label
            htmlFor="departure-time"
            className="text-xs font-medium text-muted-foreground flex items-center gap-1.5"
          >
            <Clock className="w-3.5 h-3.5 text-emerald-600" />
            預計出發時間
          </Label>
          <Input
            id="departure-time"
            type="time"
            value={departureTime}
            onChange={(e) => onDepartureTimeChange(e.target.value)}
            className={cn(aura.glassInset, "h-10 rounded-xl border-white/50")}
          />
        </div>

        <div className="space-y-2">
          <Label className="text-xs font-medium text-muted-foreground flex items-center justify-between gap-2">
            <span className="flex items-center gap-1.5">
              <Battery className={cn("w-3.5 h-3.5", isLowBattery ? "text-destructive" : "text-emerald-600")} />
              目前電池剩餘電量
            </span>
            <span
              className={cn(
                "font-bold tabular-nums text-sm",
                isLowBattery ? "text-destructive" : "text-emerald-600"
              )}
            >
              {batteryPercent}%
            </span>
          </Label>
          <Slider
            value={[batteryPercent]}
            onValueChange={([v]) => onBatteryPercentChange(v)}
            min={0}
            max={100}
            step={1}
            className="py-2"
          />
          <div className="flex justify-between text-[10px] text-muted-foreground px-0.5">
            <span>0%</span>
            <span
              className={cn(
                "flex items-center gap-0.5",
                isLowBattery && "text-destructive font-semibold"
              )}
            >
              {isLowBattery && <AlertTriangle className="w-3 h-3" />}
              低電量 &lt; 20%
            </span>
            <span>100%</span>
          </div>
        </div>
      </div>

      {error && (
        <p className="relative text-xs text-destructive bg-destructive/10 border border-destructive/20 rounded-xl px-3 py-2">
          {error}
        </p>
      )}

      <Button
        type="button"
        onClick={onSearch}
        disabled={isLoading}
        className={cn("w-full h-12 rounded-xl font-semibold text-base gap-2", aura.btnPrimary)}
      >
        {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
        {isLoading ? "AI 推薦計算中…" : "開始計算 / 搜尋"}
      </Button>
    </div>
  )
}
