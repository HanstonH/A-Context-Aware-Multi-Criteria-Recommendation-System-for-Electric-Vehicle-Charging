"use client"

import { useState } from "react"
import {
  Menu,
  Search,
  Mic,
  Home,
  Building2,
  Utensils,
  Fuel,
  Plus,
  Minus,
  Navigation,
  Layers,
  MapPin,
} from "lucide-react"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"

interface MapScreenProps {
  onMenuClick: () => void
  onSearchClick: () => void
  onNavigate: (destination: string) => void
}

const quickActions = [
  { icon: Home, label: "住家", color: "bg-primary" },
  { icon: Building2, label: "公司", color: "bg-card" },
  { icon: Utensils, label: "餐廳", color: "bg-card" },
  { icon: Fuel, label: "加油站", color: "bg-card" },
]

const markers = [
  { id: 1, name: "臭臭鍋", type: "restaurant", top: "30%", left: "35%" },
  { id: 2, name: "吳宗憲", type: "person", top: "40%", left: "40%" },
  { id: 3, name: "辦公室", type: "office", top: "55%", left: "50%" },
]

export function MapScreen({ onMenuClick, onSearchClick, onNavigate }: MapScreenProps) {
  const [zoomLevel, setZoomLevel] = useState(15)

  return (
    <div className="h-full flex flex-col bg-background">
      {/* Header */}
      <div className="absolute top-0 left-0 right-0 z-10 p-4 space-y-3">
        {/* Top Bar */}
        <div className="flex items-center gap-3">
          <button
            onClick={onMenuClick}
            className="w-10 h-10 rounded-full bg-card/90 backdrop-blur flex items-center justify-center text-foreground"
          >
            <Menu className="w-5 h-5" />
          </button>

          <div className="flex-1 flex items-center justify-center">
            <div className="flex items-center gap-2">
              <MapPin className="w-5 h-5 text-primary" />
              <span className="font-semibold text-foreground">MapExplore</span>
            </div>
          </div>

          <Avatar className="w-10 h-10 border-2 border-primary">
            <AvatarImage src="/avatar.jpg" />
            <AvatarFallback className="bg-primary text-primary-foreground">ME</AvatarFallback>
          </Avatar>
        </div>

        {/* Search Bar */}
        <div
          onClick={onSearchClick}
          className="flex items-center gap-3 bg-card/90 backdrop-blur rounded-xl px-4 py-3 cursor-pointer"
        >
          <Search className="w-5 h-5 text-muted-foreground" />
          <span className="flex-1 text-muted-foreground">搜尋目的地...</span>
          <Mic className="w-5 h-5 text-muted-foreground" />
        </div>

        {/* Quick Actions */}
        <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-hide">
          {quickActions.map((action) => (
            <button
              key={action.label}
              onClick={() => onNavigate(action.label)}
              className={`flex items-center gap-2 px-4 py-2 rounded-full ${action.color} text-foreground whitespace-nowrap text-sm`}
            >
              <action.icon className="w-4 h-4" />
              {action.label}
            </button>
          ))}
        </div>
      </div>

      {/* Map Area */}
      <div className="flex-1 relative bg-[#1a2f2f] overflow-hidden">
        {/* Grid Pattern for Map */}
        <div
          className="absolute inset-0"
          style={{
            backgroundImage: `
              linear-gradient(rgba(100, 180, 180, 0.1) 1px, transparent 1px),
              linear-gradient(90deg, rgba(100, 180, 180, 0.1) 1px, transparent 1px)
            `,
            backgroundSize: "40px 40px",
          }}
        />

        {/* Map Lines */}
        <svg className="absolute inset-0 w-full h-full" style={{ opacity: 0.3 }}>
          {/* Main roads */}
          <line x1="0" y1="50%" x2="100%" y2="50%" stroke="#4a9090" strokeWidth="3" />
          <line x1="30%" y1="0" x2="30%" y2="100%" stroke="#4a9090" strokeWidth="3" />
          <line x1="70%" y1="0" x2="70%" y2="100%" stroke="#4a9090" strokeWidth="3" />
          <line x1="0" y1="30%" x2="100%" y2="30%" stroke="#4a9090" strokeWidth="2" />
          <line x1="0" y1="70%" x2="100%" y2="70%" stroke="#4a9090" strokeWidth="2" />
          <line x1="50%" y1="0" x2="50%" y2="100%" stroke="#4a9090" strokeWidth="2" />

          {/* Diagonal roads */}
          <line x1="20%" y1="20%" x2="80%" y2="80%" stroke="#3a7070" strokeWidth="2" />
          <line x1="80%" y1="20%" x2="20%" y2="80%" stroke="#3a7070" strokeWidth="2" />
        </svg>

        {/* Location Markers */}
        {markers.map((marker) => (
          <div
            key={marker.id}
            className="absolute transform -translate-x-1/2 -translate-y-1/2"
            style={{ top: marker.top, left: marker.left }}
          >
            <div className="flex flex-col items-center">
              <div
                className={`
                w-10 h-10 rounded-full flex items-center justify-center shadow-lg
                ${marker.type === "restaurant" ? "bg-primary" : marker.type === "office" ? "bg-orange-500" : "bg-card"}
              `}
              >
                {marker.type === "restaurant" && <Utensils className="w-5 h-5 text-white" />}
                {marker.type === "office" && <Building2 className="w-5 h-5 text-white" />}
                {marker.type === "person" && <span className="text-sm">👤</span>}
              </div>
              <div className="mt-1 px-2 py-1 bg-card/90 rounded text-xs text-foreground whitespace-nowrap">
                {marker.name}
              </div>
            </div>
          </div>
        ))}

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
            <Layers className="w-5 h-5" />
          </button>
        </div>

        {/* Navigate Button */}
        <button className="absolute right-4 bottom-24 w-12 h-12 rounded-full bg-primary flex items-center justify-center text-primary-foreground shadow-lg">
          <Navigation className="w-6 h-6" />
        </button>
      </div>
    </div>
  )
}
