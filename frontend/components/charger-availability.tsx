"use client"

import { PlugZap } from "lucide-react"
import { cn } from "@/lib/utils"
import {
  AVAILABILITY_THEME,
  CONNECTOR_LABELS,
  formatAvailabilityLabel,
  getAvailabilityLight,
  getAvailabilityPercent,
  type AvailabilityLight,
  type ConnectorAvailability,
  type StationStatus,
} from "@/lib/charger-availability"

export function AvailabilityCountLabel({
  available,
  total,
  status,
  className,
}: {
  available: number
  total: number
  status?: StationStatus
  className?: string
}) {
  const light = getAvailabilityLight(available, total, status)
  const theme = AVAILABILITY_THEME[light]

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-[11px] font-bold tabular-nums",
        theme.badge,
        className
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full shrink-0", theme.dot)} />
      {light === "gray" ? theme.label : formatAvailabilityLabel(available, total)}
    </span>
  )
}

export function AvailabilityProgressBar({
  available,
  total,
  status,
  className,
}: {
  available: number
  total: number
  status?: StationStatus
  className?: string
}) {
  const light = getAvailabilityLight(available, total, status)
  const theme = AVAILABILITY_THEME[light]
  const percent = getAvailabilityPercent(available, total)

  return (
    <div className={cn("space-y-1.5", className)}>
      <div className="flex items-baseline justify-between gap-2">
        <p className={cn("text-sm font-bold tabular-nums", theme.text)}>
          {formatAvailabilityLabel(available, total)}
        </p>
        <p className="text-[11px] font-semibold text-muted-foreground tabular-nums">{percent}%</p>
      </div>
      <div className={cn("h-2.5 w-full overflow-hidden rounded-full", theme.track)}>
        <div
          className={cn("h-full rounded-full transition-all duration-500 ease-out", theme.bar)}
          style={{ width: `${percent}%` }}
        />
      </div>
      <p className={cn("text-[11px] font-medium", theme.text)}>
        {theme.emoji} {theme.label}
      </p>
    </div>
  )
}

export function ConnectorBreakdown({
  ports,
  className,
}: {
  ports: ConnectorAvailability[]
  className?: string
}) {
  if (!ports.length) return null

  return (
    <div className={cn("space-y-2", className)}>
      <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
        各型號空槍
      </p>
      <div className="space-y-2">
        {ports.map((port) => {
          const light = getAvailabilityLight(port.available, port.total)
          const theme = AVAILABILITY_THEME[light]
          const percent = getAvailabilityPercent(port.available, port.total)
          return (
            <div key={port.type} className="space-y-1">
              <div className="flex items-center justify-between gap-2 text-[12px]">
                <span className="font-semibold text-foreground">{CONNECTOR_LABELS[port.type]}</span>
                <span className={cn("font-bold tabular-nums", theme.text)}>
                  {port.available}/{port.total}
                </span>
              </div>
              <div className={cn("h-1.5 w-full overflow-hidden rounded-full", theme.track)}>
                <div
                  className={cn("h-full rounded-full transition-all duration-500", theme.bar)}
                  style={{ width: `${percent}%` }}
                />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export function StationAvailabilityCard({
  available,
  total,
  status,
  ports,
  className,
}: {
  available: number
  total: number
  status?: StationStatus
  ports?: ConnectorAvailability[]
  className?: string
}) {
  return (
    <div
      className={cn(
        "rounded-xl border border-black/5 dark:border-white/10 bg-muted/50 p-3 space-y-3",
        className
      )}
    >
      <div className="flex items-center gap-1.5 text-[11px] font-semibold text-muted-foreground">
        <PlugZap className="w-3.5 h-3.5" />
        即時空槍狀態
      </div>
      <AvailabilityProgressBar available={available} total={total} status={status} />
      <ConnectorBreakdown ports={ports ?? []} />
    </div>
  )
}

export function AvailabilityLegend({ className }: { className?: string }) {
  const items: AvailabilityLight[] = ["green", "yellow", "red", "gray"]
  return (
    <div className={cn("flex flex-wrap gap-x-2.5 gap-y-1", className)}>
      {items.map((light) => {
        const theme = AVAILABILITY_THEME[light]
        return (
          <span key={light} className="inline-flex items-center gap-1 text-[10px] text-muted-foreground">
            <span className={cn("h-2 w-2 rounded-full", theme.dot)} />
            {theme.label}
          </span>
        )
      })}
    </div>
  )
}
