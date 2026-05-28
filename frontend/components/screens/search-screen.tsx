"use client"

import { useState } from "react"
import { ArrowLeft, X, MapPin, Home, Building2, ChevronRight, Sparkles } from "lucide-react"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"

interface SearchScreenProps {
  onBack: () => void
  onSelectLocation: (location: string) => void
}

const recentSearches = [
  {
    id: 1,
    name: "台北101",
    address: "台北市信義區信義路五段 7 號",
    icon: MapPin,
    color: "bg-primary",
  },
  {
    id: 2,
    name: "誠品生活松菸店",
    address: "台北市信義區菸廠路 88 號",
    icon: MapPin,
    color: "bg-primary",
  },
  {
    id: 3,
    name: "大安森林公園",
    address: "台北市大安區新生南路二段 1 號",
    icon: MapPin,
    color: "bg-primary",
  },
]

const favoriteLocations = [
  {
    id: 1,
    name: "住家",
    address: "新北市中和區景安路101巷12號5樓",
    icon: Home,
    color: "bg-primary",
  },
  {
    id: 2,
    name: "公司",
    address: "台北市中山區南京東路三段 219 號",
    icon: Building2,
    color: "bg-muted",
  },
]

export function SearchScreen({ onBack, onSelectLocation }: SearchScreenProps) {
  const [searchQuery, setSearchQuery] = useState("")

  return (
    <div className="h-full flex flex-col bg-background">
      {/* Header */}
      <div className="p-4 space-y-4 border-b border-border">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="w-10 h-10 rounded-full bg-card flex items-center justify-center text-foreground"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div className="flex-1 relative">
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="搜尋地點..."
              className="h-11 bg-card border-none rounded-xl pl-4 pr-10 text-foreground placeholder:text-muted-foreground"
              autoFocus
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery("")}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground"
              >
                <X className="w-5 h-5" />
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {/* Recent Searches */}
        <div className="p-4">
          <div className="flex justify-between items-center mb-3">
            <h2 className="text-sm font-medium text-muted-foreground">最近搜尋</h2>
            <button className="text-sm text-primary">清除全部</button>
          </div>
          <div className="space-y-2">
            {recentSearches.map((item) => (
              <button
                key={item.id}
                onClick={() => onSelectLocation(item.name)}
                className="w-full flex items-center gap-3 p-3 bg-card rounded-xl hover:bg-card/80 transition-colors"
              >
                <div className={`w-10 h-10 rounded-full ${item.color} flex items-center justify-center`}>
                  <item.icon className="w-5 h-5 text-primary-foreground" />
                </div>
                <div className="flex-1 text-left">
                  <p className="font-medium text-foreground">{item.name}</p>
                  <p className="text-sm text-muted-foreground">{item.address}</p>
                </div>
                <ChevronRight className="w-5 h-5 text-muted-foreground" />
              </button>
            ))}
          </div>
        </div>

        {/* Favorite Locations */}
        <div className="p-4">
          <div className="flex justify-between items-center mb-3">
            <h2 className="text-sm font-medium text-muted-foreground">喜愛地點</h2>
            <button className="text-sm text-primary">管理</button>
          </div>
          <div className="space-y-2">
            {favoriteLocations.map((item) => (
              <button
                key={item.id}
                onClick={() => onSelectLocation(item.name)}
                className="w-full flex items-center gap-3 p-3 bg-card rounded-xl hover:bg-card/80 transition-colors"
              >
                <div className={`w-10 h-10 rounded-full ${item.color} flex items-center justify-center`}>
                  <item.icon className="w-5 h-5 text-primary-foreground" />
                </div>
                <div className="flex-1 text-left">
                  <p className="font-medium text-foreground">{item.name}</p>
                  <p className="text-sm text-muted-foreground">{item.address}</p>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Explore Banner */}
        <div className="p-4">
          <div className="relative rounded-2xl overflow-hidden h-40">
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
              <div className="flex items-center gap-2">
                <div className="flex -space-x-2">
                  <div className="w-6 h-6 rounded-full bg-primary border-2 border-background" />
                  <div className="w-6 h-6 rounded-full bg-accent border-2 border-background" />
                  <div className="w-6 h-6 rounded-full bg-muted border-2 border-background" />
                </div>
                <Button size="sm" className="ml-auto bg-primary hover:bg-primary/90 text-primary-foreground rounded-full">
                  開始探索
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
