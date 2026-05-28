"use client"

import { useState } from "react"
import {
  Menu,
  Plus,
  Minus,
  Layers,
  Navigation,
  CornerUpLeft,
  MapPin,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"

interface NavigationScreenProps {
  destination: string
  onMenuClick: () => void
  onStartNavigation: () => void
  onClose: () => void
}

export function NavigationScreen({
  destination,
  onMenuClick,
  onStartNavigation,
  onClose,
}: NavigationScreenProps) {
  const [zoomLevel, setZoomLevel] = useState(15)

  return (
    <div className="h-full flex flex-col bg-background">
      {/* Header */}
      <div className="p-4 flex items-center gap-3">
        <button
          onClick={onMenuClick}
          className="w-10 h-10 rounded-full bg-card/90 backdrop-blur flex items-center justify-center text-foreground"
        >
          <Menu className="w-5 h-5" />
        </button>
        <div className="flex-1 flex items-center justify-center gap-2">
          <MapPin className="w-5 h-5 text-primary" />
          <span className="font-semibold text-foreground">MapExplore</span>
        </div>
        <Avatar className="w-10 h-10 border-2 border-primary">
          <AvatarImage src="/avatar.jpg" />
          <AvatarFallback className="bg-primary text-primary-foreground">ME</AvatarFallback>
        </Avatar>
      </div>

      {/* Direction Card */}
      <div className="mx-4 p-4 bg-card rounded-2xl">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-primary flex items-center justify-center">
            <CornerUpLeft className="w-6 h-6 text-primary-foreground" />
          </div>
          <div className="flex-1">
            <p className="text-sm text-muted-foreground">下個轉彎處</p>
            <p className="font-semibold text-foreground">向左轉進入中山路</p>
          </div>
          <div className="text-right">
            <span className="text-2xl font-bold text-primary">350</span>
            <span className="text-sm text-primary">m</span>
          </div>
        </div>
      </div>

      {/* Map Area */}
      <div className="flex-1 relative bg-[#1a2f2f] overflow-hidden mt-4">
        {/* Grid Pattern for Map */}
        <div
          className="absolute inset-0"
          style={{
            backgroundImage: `
              linear-gradient(rgba(100, 180, 180, 0.1) 1px, transparent 1px),
              linear-gradient(90deg, rgba(100, 180, 180, 0.1) 1px, transparent 1px)
            `,
            backgroundSize: "30px 30px",
          }}
        />

        {/* Route visualization */}
        <svg className="absolute inset-0 w-full h-full">
          {/* Roads */}
          <line x1="0" y1="50%" x2="100%" y2="50%" stroke="rgba(74, 144, 144, 0.3)" strokeWidth="3" />
          <line x1="30%" y1="0" x2="30%" y2="100%" stroke="rgba(74, 144, 144, 0.3)" strokeWidth="3" />
          <line x1="70%" y1="0" x2="70%" y2="100%" stroke="rgba(74, 144, 144, 0.3)" strokeWidth="3" />

          {/* Navigation Route */}
          <path
            d="M 50% 90% L 50% 50% L 30% 50% L 30% 20%"
            fill="none"
            stroke="hsl(180, 60%, 50%)"
            strokeWidth="6"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeDasharray="12 6"
          />

          {/* Current position indicator */}
          <circle cx="50%" cy="85%" r="12" fill="hsl(180, 60%, 50%)" />
          <circle cx="50%" cy="85%" r="8" fill="white" />
          <circle cx="50%" cy="85%" r="4" fill="hsl(180, 60%, 50%)" />

          {/* Destination marker */}
          <circle cx="30%" cy="20%" r="10" fill="hsl(0, 70%, 50%)" />
          <circle cx="30%" cy="20%" r="6" fill="white" />
        </svg>

        {/* Map Controls */}
        <div className="absolute right-4 top-1/2 -translate-y-1/2 flex flex-col gap-2">
          <button
            onClick={() => setZoomLevel((z) => Math.min(z + 1, 20))}
            className="w-10 h-10 rounded-full bg-card/90 backdrop-blur flex items-center justify-center text-foreground shadow-lg"
          >
            <Plus className="w-5 h-5" />
          </button>
          <button
            onClick={() => setZoomLevel((z) => Math.max(z - 1, 1))}
            className="w-10 h-10 rounded-full bg-card/90 backdrop-blur flex items-center justify-center text-foreground shadow-lg"
          >
            <Minus className="w-5 h-5" />
          </button>
          <button className="w-10 h-10 rounded-full bg-card/90 backdrop-blur flex items-center justify-center text-foreground shadow-lg">
            <Navigation className="w-5 h-5" />
          </button>
          <button className="w-10 h-10 rounded-full bg-card/90 backdrop-blur flex items-center justify-center text-foreground shadow-lg">
            <Layers className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Bottom Navigation Info */}
      <div className="p-4 bg-card rounded-t-3xl">
        <div className="flex items-center justify-between mb-4">
          <div className="text-center">
            <p className="text-xs text-muted-foreground">預估時間</p>
            <div className="flex items-baseline gap-1">
              <span className="text-3xl font-bold text-foreground">15</span>
              <span className="text-sm text-muted-foreground">分鐘</span>
            </div>
            <p className="text-xs text-primary">交通暢順</p>
          </div>
          <div className="h-12 w-px bg-border" />
          <div className="text-center">
            <p className="text-xs text-muted-foreground">距離</p>
            <div className="flex items-baseline gap-1">
              <span className="text-3xl font-bold text-foreground">5.2</span>
              <span className="text-sm text-muted-foreground">公里</span>
            </div>
            <p className="text-xs text-muted-foreground">經由建國高架橋</p>
          </div>
        </div>

        <div className="flex gap-3">
          <Button
            onClick={onStartNavigation}
            className="flex-1 h-14 bg-primary hover:bg-primary/90 text-primary-foreground rounded-2xl font-medium text-lg"
          >
            <Navigation className="w-5 h-5 mr-2" />
            開始導航
          </Button>
          <button className="w-14 h-14 rounded-2xl bg-muted flex items-center justify-center text-foreground">
            <Layers className="w-6 h-6" />
          </button>
        </div>
      </div>
    </div>
  )
}
