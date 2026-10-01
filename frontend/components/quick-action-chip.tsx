"use client"

import type { LucideIcon } from "lucide-react"
import { cn } from "@/lib/utils"

interface QuickActionChipProps {
  icon: LucideIcon
  label: string
  selected?: boolean
  onClick: () => void
  className?: string
}

export function QuickActionChip({
  icon: Icon,
  label,
  selected = false,
  onClick,
  className,
}: QuickActionChipProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex items-center gap-2 px-4 py-2.5 rounded-full text-sm font-medium",
        "border backdrop-blur-md transition-all duration-300",
        "hover:shadow-md active:scale-95",
        selected
          ? "scale-105 bg-emerald-600 text-white border-emerald-500/50 shadow-lg shadow-emerald-600/30 ring-2 ring-emerald-400/50 drop-shadow-[0_0_12px_rgba(16,185,129,0.35)]"
          : "bg-white/70 dark:bg-zinc-900/60 text-foreground border-white/50 dark:border-white/10 shadow-sm hover:bg-white/90 hover:border-emerald-300/40 dark:hover:border-emerald-500/30",
        className
      )}
    >
      <Icon className={cn("w-4 h-4", selected && "drop-shadow-sm")} />
      {label}
    </button>
  )
}
