"use client"

import { useState } from "react"
import {
  Plus,
  Minus,
  Navigation,
  Layers,
  MapPin,
  Utensils,
  Building2,
  CornerUpLeft,
  X,
} from "lucide-react"
import { cn } from "@/lib/utils"

interface MapViewProps {
  selectedDestination: string | null
  isNavigating: boolean
  onClose?: () => void
}

const markers = [
  { id: 1, name: "臭臭鍋", type: "restaurant", top: "35%", left: "40%" },
  { id: 2, name: "吳宗憲", type: "person", top: "45%", left: "55%" },
  { id: 3, name: "辦公室", type: "office", top: "60%", left: "45%" },
  { id: 4, name: "台北101", type: "landmark", top: "30%", left: "65%" },
  { id: 5, name: "誠品生活", type: "shop", top: "55%", left: "70%" },
]

export function MapView({ selectedDestination, isNavigating, onClose }: MapViewProps) {
  const [zoomLevel, setZoomLevel] = useState(15)

  return (
    <div className="relative w-full h-full bg-[#e8f4f4] dark:bg-[#1a2f2f] overflow-hidden transition-colors duration-300">
      {/* Grid Pattern for Map */}
      <div
        className="absolute inset-0 transition-opacity duration-300"
        style={{
          backgroundImage: `
            linear-gradient(rgba(50, 120, 120, 0.12) 1px, transparent 1px),
            linear-gradient(90deg, rgba(50, 120, 120, 0.12) 1px, transparent 1px)
          `,
          backgroundSize: `${40 * (zoomLevel / 15)}px ${40 * (zoomLevel / 15)}px`,
        }}
      />
      <div
        className="absolute inset-0 hidden dark:block transition-opacity duration-300"
        style={{
          backgroundImage: `
            linear-gradient(rgba(100, 180, 180, 0.08) 1px, transparent 1px),
            linear-gradient(90deg, rgba(100, 180, 180, 0.08) 1px, transparent 1px)
          `,
          backgroundSize: `${40 * (zoomLevel / 15)}px ${40 * (zoomLevel / 15)}px`,
        }}
      />

      {/* Map Lines - Roads (Light Mode) */}
      <svg className="absolute inset-0 w-full h-full dark:hidden" style={{ opacity: 0.6 }}>
        {/* Main roads */}
        <line x1="0" y1="50%" x2="100%" y2="50%" stroke="#ffffff" strokeWidth="6" />
        <line x1="0" y1="30%" x2="100%" y2="30%" stroke="#ffffff" strokeWidth="4" />
        <line x1="0" y1="70%" x2="100%" y2="70%" stroke="#ffffff" strokeWidth="4" />
        <line x1="25%" y1="0" x2="25%" y2="100%" stroke="#ffffff" strokeWidth="6" />
        <line x1="50%" y1="0" x2="50%" y2="100%" stroke="#ffffff" strokeWidth="4" />
        <line x1="75%" y1="0" x2="75%" y2="100%" stroke="#ffffff" strokeWidth="6" />

        {/* Secondary roads */}
        <line x1="0" y1="40%" x2="100%" y2="40%" stroke="#ffffff" strokeWidth="3" />
        <line x1="0" y1="60%" x2="100%" y2="60%" stroke="#ffffff" strokeWidth="3" />
        <line x1="35%" y1="0" x2="35%" y2="100%" stroke="#ffffff" strokeWidth="3" />
        <line x1="60%" y1="0" x2="60%" y2="100%" stroke="#ffffff" strokeWidth="3" />
        <line x1="85%" y1="0" x2="85%" y2="100%" stroke="#ffffff" strokeWidth="3" />

        {/* Diagonal roads */}
        <line x1="10%" y1="20%" x2="40%" y2="80%" stroke="#ffffff" strokeWidth="3" />
        <line x1="60%" y1="15%" x2="90%" y2="85%" stroke="#ffffff" strokeWidth="3" />
      </svg>

      {/* Road outlines (Light Mode) */}
      <svg className="absolute inset-0 w-full h-full dark:hidden" style={{ opacity: 0.2 }}>
        <line x1="0" y1="50%" x2="100%" y2="50%" stroke="#2a7070" strokeWidth="8" />
        <line x1="25%" y1="0" x2="25%" y2="100%" stroke="#2a7070" strokeWidth="8" />
        <line x1="75%" y1="0" x2="75%" y2="100%" stroke="#2a7070" strokeWidth="8" />
      </svg>

      {/* Map Lines - Roads (Dark Mode) */}
      <svg className="absolute inset-0 w-full h-full hidden dark:block" style={{ opacity: 0.4 }}>
        {/* Main roads */}
        <line x1="0" y1="50%" x2="100%" y2="50%" stroke="#4a9090" strokeWidth="4" />
        <line x1="0" y1="30%" x2="100%" y2="30%" stroke="#4a9090" strokeWidth="3" />
        <line x1="0" y1="70%" x2="100%" y2="70%" stroke="#4a9090" strokeWidth="3" />
        <line x1="25%" y1="0" x2="25%" y2="100%" stroke="#4a9090" strokeWidth="4" />
        <line x1="50%" y1="0" x2="50%" y2="100%" stroke="#4a9090" strokeWidth="3" />
        <line x1="75%" y1="0" x2="75%" y2="100%" stroke="#4a9090" strokeWidth="4" />

        {/* Secondary roads */}
        <line x1="0" y1="40%" x2="100%" y2="40%" stroke="#3a7070" strokeWidth="2" />
        <line x1="0" y1="60%" x2="100%" y2="60%" stroke="#3a7070" strokeWidth="2" />
        <line x1="35%" y1="0" x2="35%" y2="100%" stroke="#3a7070" strokeWidth="2" />
        <line x1="60%" y1="0" x2="60%" y2="100%" stroke="#3a7070" strokeWidth="2" />
        <line x1="85%" y1="0" x2="85%" y2="100%" stroke="#3a7070" strokeWidth="2" />

        {/* Diagonal roads */}
        <line x1="10%" y1="20%" x2="40%" y2="80%" stroke="#3a7070" strokeWidth="2" />
        <line x1="60%" y1="15%" x2="90%" y2="85%" stroke="#3a7070" strokeWidth="2" />
      </svg>

      {/* Navigation Route (when navigating) */}
      {selectedDestination && (
        <svg className="absolute inset-0 w-full h-full pointer-events-none">
          <defs>
            <linearGradient id="routeGradient" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="hsl(180, 65%, 40%)" />
              <stop offset="100%" stopColor="hsl(180, 70%, 35%)" />
            </linearGradient>
          </defs>
          <path
            d="M 50% 75% Q 50% 55% 45% 50% T 35% 35%"
            fill="none"
            stroke="url(#routeGradient)"
            strokeWidth="8"
            strokeLinecap="round"
            strokeLinejoin="round"
            className={cn(isNavigating && "animate-pulse")}
          />
          {isNavigating && (
            <path
              d="M 50% 75% Q 50% 55% 45% 50% T 35% 35%"
              fill="none"
              stroke="white"
              strokeWidth="3"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeDasharray="10 20"
              className="animate-[dash_1s_linear_infinite]"
            />
          )}
        </svg>
      )}

      {/* Location Markers */}
      {markers.map((marker) => (
        <div
          key={marker.id}
          className="absolute transform -translate-x-1/2 -translate-y-1/2 cursor-pointer group"
          style={{ top: marker.top, left: marker.left }}
        >
          <div className="flex flex-col items-center">
            <div
              className={cn(
                "w-10 h-10 rounded-full flex items-center justify-center shadow-lg transition-transform group-hover:scale-110",
                marker.type === "restaurant" && "bg-primary",
                marker.type === "office" && "bg-orange-500",
                marker.type === "landmark" && "bg-red-500",
                marker.type === "shop" && "bg-purple-500",
                marker.type === "person" && "bg-card border-2 border-primary"
              )}
            >
              {marker.type === "restaurant" && <Utensils className="w-5 h-5 text-white" />}
              {marker.type === "office" && <Building2 className="w-5 h-5 text-white" />}
              {marker.type === "landmark" && <MapPin className="w-5 h-5 text-white" />}
              {marker.type === "shop" && <MapPin className="w-5 h-5 text-white" />}
              {marker.type === "person" && <span className="text-lg">👤</span>}
            </div>
            <div className="mt-1 px-2 py-1 bg-card/95 backdrop-blur rounded text-xs text-foreground whitespace-nowrap shadow-lg opacity-0 group-hover:opacity-100 transition-opacity border border-border">
              {marker.name}
            </div>
          </div>
        </div>
      ))}

      {/* Current Position */}
      <div
        className="absolute transform -translate-x-1/2 -translate-y-1/2"
        style={{ top: "75%", left: "50%" }}
      >
        <div className="relative">
          <div className="w-6 h-6 rounded-full bg-primary border-4 border-white shadow-lg" />
          <div className="absolute inset-0 w-6 h-6 rounded-full bg-primary/50 animate-ping" />
        </div>
      </div>

      {/* Destination Marker (when navigating) */}
      {selectedDestination && (
        <div
          className="absolute transform -translate-x-1/2 -translate-y-1/2"
          style={{ top: "35%", left: "35%" }}
        >
          <div className="flex flex-col items-center">
            <div className="w-12 h-12 rounded-full bg-destructive flex items-center justify-center shadow-lg">
              <MapPin className="w-6 h-6 text-white" />
            </div>
            <div className="mt-1 px-3 py-1.5 bg-card/95 backdrop-blur rounded-lg text-sm text-foreground whitespace-nowrap shadow-lg font-medium border border-border">
              {selectedDestination}
            </div>
          </div>
        </div>
      )}

      {/* Navigation Direction Card (when navigating) */}
      {isNavigating && (
        <div className="absolute top-4 left-4 right-4 md:left-auto md:right-4 md:w-80">
          <div className="bg-card/95 backdrop-blur rounded-2xl p-4 shadow-xl">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-primary flex items-center justify-center shrink-0">
                <CornerUpLeft className="w-6 h-6 text-primary-foreground" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-muted-foreground">下個轉彎處</p>
                <p className="font-semibold text-foreground">向左轉進入中山路</p>
              </div>
              <div className="text-right shrink-0">
                <span className="text-2xl font-bold text-primary">350</span>
                <span className="text-sm text-primary">m</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Map Controls */}
      <div className="absolute right-4 top-1/2 -translate-y-1/2 flex flex-col gap-2">
        <button
          onClick={() => setZoomLevel((z) => Math.min(z + 1, 20))}
          className="w-10 h-10 rounded-full bg-card shadow-md flex items-center justify-center text-foreground hover:bg-muted transition-colors border border-border"
        >
          <Plus className="w-5 h-5" />
        </button>
        <button
          onClick={() => setZoomLevel((z) => Math.max(z - 1, 1))}
          className="w-10 h-10 rounded-full bg-card shadow-md flex items-center justify-center text-foreground hover:bg-muted transition-colors border border-border"
        >
          <Minus className="w-5 h-5" />
        </button>
        <div className="h-2" />
        <button className="w-10 h-10 rounded-full bg-card shadow-md flex items-center justify-center text-foreground hover:bg-muted transition-colors border border-border">
          <Navigation className="w-5 h-5" />
        </button>
        <button className="w-10 h-10 rounded-full bg-card shadow-md flex items-center justify-center text-foreground hover:bg-muted transition-colors border border-border">
          <Layers className="w-5 h-5" />
        </button>
      </div>

      {/* Close Navigation Button */}
      {selectedDestination && onClose && (
        <button
          onClick={onClose}
          className="absolute top-4 right-4 w-10 h-10 rounded-full bg-card shadow-md flex items-center justify-center text-foreground hover:bg-muted transition-colors border border-border md:hidden"
        >
          <X className="w-5 h-5" />
        </button>
      )}

      {/* Zoom Level Indicator */}
      <div className="absolute bottom-4 left-4 px-3 py-1.5 bg-card/95 backdrop-blur rounded-full text-xs text-muted-foreground shadow-md border border-border">
        縮放 {zoomLevel}x
      </div>
    </div>
  )
}
