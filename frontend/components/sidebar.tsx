"use client"

import { useState } from "react"
import {
  Search,
  Mic,
  Home,
  Building2,
  Utensils,
  Fuel,
  MapPin,
  ChevronRight,
  Clock,
  Heart,
  Sparkles,
  ArrowLeft,
  X,
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
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { cn } from "@/lib/utils"

type SidebarView = "main" | "search" | "settings" | "navigation"

interface SidebarProps {
  onNavigate: (destination: string) => void
  onLogout: () => void
  selectedDestination: string | null
  isNavigating: boolean
  onStartNavigation: () => void
  onCancelNavigation: () => void
  darkMode: boolean
  onDarkModeChange: (value: boolean) => void
}

const quickActions = [
  { icon: Home, label: "住家", color: "bg-primary" },
  { icon: Building2, label: "公司", color: "bg-card hover:bg-muted" },
  { icon: Utensils, label: "餐廳", color: "bg-card hover:bg-muted" },
  { icon: Fuel, label: "加油站", color: "bg-card hover:bg-muted" },
]

const recentSearches = [
  { id: 1, name: "台北101", address: "台北市信義區信義路五段 7 號" },
  { id: 2, name: "誠品生活松菸店", address: "台北市信義區菸廠路 88 號" },
  { id: 3, name: "大安森林公園", address: "台北市大安區新生南路二段 1 號" },
]

const favoriteLocations = [
  { id: 1, name: "住家", address: "新北市中和區景安路101巷12號5樓", icon: Home },
  { id: 2, name: "公司", address: "台北市中山區南京東路三段 219 號", icon: Building2 },
]

export function Sidebar({
  onNavigate,
  onLogout,
  selectedDestination,
  isNavigating,
  onStartNavigation,
  onCancelNavigation,
  darkMode,
  onDarkModeChange,
}: SidebarProps) {
  const [view, setView] = useState<SidebarView>("main")
  const [searchQuery, setSearchQuery] = useState("")
  const [trafficAlerts, setTrafficAlerts] = useState(true)
  const [isCollapsed, setIsCollapsed] = useState(false)

  const handleSelectLocation = (location: string) => {
    onNavigate(location)
    setView("navigation")
  }

  // Collapsed sidebar
  if (isCollapsed) {
    return (
      <div className="w-16 h-full bg-sidebar border-r border-sidebar-border flex flex-col items-center py-4 gap-4">
        <button
          onClick={() => setIsCollapsed(false)}
          className="w-10 h-10 rounded-full bg-card flex items-center justify-center text-foreground hover:bg-muted transition-colors"
        >
          <Menu className="w-5 h-5" />
        </button>
        <div className="w-10 h-10 rounded-full bg-primary/20 flex items-center justify-center">
          <MapPin className="w-5 h-5 text-primary" />
        </div>
        <div className="flex-1" />
        <button
          onClick={() => {
            setIsCollapsed(false)
            setView("settings")
          }}
          className="w-10 h-10 rounded-full bg-card flex items-center justify-center text-foreground hover:bg-muted transition-colors"
        >
          <Settings className="w-5 h-5" />
        </button>
        <Avatar className="w-10 h-10 border-2 border-primary cursor-pointer">
          <AvatarImage src="/avatar.jpg" />
          <AvatarFallback className="bg-primary text-primary-foreground text-sm">ME</AvatarFallback>
        </Avatar>
      </div>
    )
  }

  return (
    <div className="w-96 h-full bg-sidebar border-r border-sidebar-border flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-sidebar-border">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setIsCollapsed(true)}
              className="w-10 h-10 rounded-full bg-card flex items-center justify-center text-foreground hover:bg-muted transition-colors"
            >
              <Menu className="w-5 h-5" />
            </button>
            <div className="flex items-center gap-2">
              <MapPin className="w-5 h-5 text-primary" />
              <span className="font-semibold text-foreground text-lg">MapExplore</span>
            </div>
          </div>
          <Avatar className="w-10 h-10 border-2 border-primary cursor-pointer">
            <AvatarImage src="/avatar.jpg" />
            <AvatarFallback className="bg-primary text-primary-foreground text-sm">ME</AvatarFallback>
          </Avatar>
        </div>

        {/* Search Bar */}
        <div
          onClick={() => setView("search")}
          className={cn(
            "flex items-center gap-3 bg-card rounded-xl px-4 py-3 cursor-pointer hover:bg-muted transition-colors border border-border shadow-sm",
            view === "search" && "ring-2 ring-primary"
          )}
        >
          <Search className="w-5 h-5 text-muted-foreground" />
          <span className="flex-1 text-muted-foreground">搜尋目的地...</span>
          <Mic className="w-5 h-5 text-muted-foreground" />
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {view === "main" && (
          <div className="p-4 space-y-6">
            {/* Quick Actions */}
            <div className="flex flex-wrap gap-2">
              {quickActions.map((action) => (
                <button
                  key={action.label}
                  onClick={() => handleSelectLocation(action.label)}
                  className={cn(
                    "flex items-center gap-2 px-4 py-2 rounded-full text-foreground text-sm transition-colors",
                    action.color
                  )}
                >
                  <action.icon className="w-4 h-4" />
                  {action.label}
                </button>
              ))}
            </div>

            {/* Recent Searches */}
            <div>
              <div className="flex items-center gap-2 mb-3 text-muted-foreground">
                <Clock className="w-4 h-4" />
                <span className="text-sm font-medium">最近搜尋</span>
              </div>
              <div className="space-y-2">
                {recentSearches.map((item) => (
                  <button
                    key={item.id}
                    onClick={() => handleSelectLocation(item.name)}
                    className="w-full flex items-center gap-3 p-3 bg-card rounded-xl hover:bg-muted transition-colors text-left border border-border shadow-sm"
                  >
                    <div className="w-10 h-10 rounded-full bg-primary flex items-center justify-center shrink-0">
                      <MapPin className="w-5 h-5 text-primary-foreground" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-foreground truncate">{item.name}</p>
                      <p className="text-sm text-muted-foreground truncate">{item.address}</p>
                    </div>
                    <ChevronRight className="w-5 h-5 text-muted-foreground shrink-0" />
                  </button>
                ))}
              </div>
            </div>

            {/* Favorite Locations */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Heart className="w-4 h-4" />
                  <span className="text-sm font-medium">喜愛地點</span>
                </div>
                <button className="text-sm text-primary hover:underline">管理</button>
              </div>
              <div className="space-y-2">
                {favoriteLocations.map((item) => (
                  <button
                    key={item.id}
                    onClick={() => handleSelectLocation(item.name)}
                    className="w-full flex items-center gap-3 p-3 bg-card rounded-xl hover:bg-muted transition-colors text-left border border-border shadow-sm"
                  >
                    <div className="w-10 h-10 rounded-full bg-primary flex items-center justify-center shrink-0">
                      <item.icon className="w-5 h-5 text-primary-foreground" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-foreground">{item.name}</p>
                      <p className="text-sm text-muted-foreground truncate">{item.address}</p>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {/* Explore Banner */}
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
                <Button size="sm" className="w-fit bg-primary hover:bg-primary/90 text-primary-foreground rounded-full">
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
                className="w-10 h-10 rounded-full bg-card flex items-center justify-center text-foreground hover:bg-muted transition-colors"
              >
                <ArrowLeft className="w-5 h-5" />
              </button>
              <div className="flex-1 relative">
                <Input
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="搜尋地點..."
                  className="h-11 bg-card border border-border rounded-xl pl-4 pr-10 text-foreground placeholder:text-muted-foreground shadow-sm"
                  autoFocus
                />
                {searchQuery && (
                  <button
                    onClick={() => setSearchQuery("")}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  >
                    <X className="w-5 h-5" />
                  </button>
                )}
              </div>
            </div>

            <div className="space-y-2">
              {recentSearches
                .filter((item) =>
                  searchQuery ? item.name.toLowerCase().includes(searchQuery.toLowerCase()) : true
                )
                .map((item) => (
                  <button
                    key={item.id}
                    onClick={() => handleSelectLocation(item.name)}
                    className="w-full flex items-center gap-3 p-3 bg-card rounded-xl hover:bg-muted transition-colors text-left border border-border shadow-sm"
                  >
                    <div className="w-10 h-10 rounded-full bg-primary flex items-center justify-center shrink-0">
                      <MapPin className="w-5 h-5 text-primary-foreground" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-foreground truncate">{item.name}</p>
                      <p className="text-sm text-muted-foreground truncate">{item.address}</p>
                    </div>
                    <ChevronRight className="w-5 h-5 text-muted-foreground shrink-0" />
                  </button>
                ))}
            </div>
          </div>
        )}

        {view === "settings" && (
          <div className="p-4 space-y-4">
            <div className="flex items-center gap-3 mb-2">
              <button
                onClick={() => setView("main")}
                className="w-10 h-10 rounded-full bg-card flex items-center justify-center text-foreground hover:bg-muted transition-colors"
              >
                <ArrowLeft className="w-5 h-5" />
              </button>
              <h2 className="text-lg font-semibold text-foreground">設定</h2>
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
                  className="w-full flex items-center gap-3 p-4 bg-card rounded-xl hover:bg-muted transition-colors border border-border shadow-sm"
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
              <div className="flex items-center justify-between p-4 bg-card rounded-xl border border-border shadow-sm">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center">
                    <Moon className="w-5 h-5 text-foreground" />
                  </div>
                  <span className="font-medium text-foreground">深色模式</span>
                </div>
                <Switch checked={darkMode} onCheckedChange={onDarkModeChange} />
              </div>

              <div className="flex items-center justify-between p-4 bg-card rounded-xl border border-border shadow-sm">
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
            <button className="w-full flex items-center gap-3 p-4 bg-card rounded-xl hover:bg-muted transition-colors border border-border shadow-sm">
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
              onClick={onLogout}
              className="w-full flex items-center justify-center gap-2 p-4 bg-card rounded-xl text-destructive hover:bg-destructive/10 transition-colors border border-border shadow-sm"
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
                className="w-10 h-10 rounded-full bg-card flex items-center justify-center text-foreground hover:bg-muted transition-colors"
              >
                <ArrowLeft className="w-5 h-5" />
              </button>
              <h2 className="text-lg font-semibold text-foreground">導航至 {selectedDestination}</h2>
            </div>

            {/* Route Info */}
            <div className="bg-card rounded-2xl p-4 space-y-4 border border-border shadow-sm">
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
                </div>
              </div>
            </div>

            {/* Time & Distance */}
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-card rounded-xl p-4 text-center border border-border shadow-sm">
                <p className="text-xs text-muted-foreground mb-1">預估時間</p>
                <div className="flex items-baseline justify-center gap-1">
                  <span className="text-3xl font-bold text-foreground">15</span>
                  <span className="text-sm text-muted-foreground">分鐘</span>
                </div>
                <p className="text-xs text-primary mt-1">交通暢順</p>
              </div>
              <div className="bg-card rounded-xl p-4 text-center border border-border shadow-sm">
                <p className="text-xs text-muted-foreground mb-1">距離</p>
                <div className="flex items-baseline justify-center gap-1">
                  <span className="text-3xl font-bold text-foreground">5.2</span>
                  <span className="text-sm text-muted-foreground">公里</span>
                </div>
                <p className="text-xs text-muted-foreground mt-1">經由建國高架橋</p>
              </div>
            </div>

            {/* Route Options */}
            <div className="space-y-2">
              <p className="text-sm font-medium text-muted-foreground">建議路線</p>
              {[
                { name: "最快路線", time: "15 分鐘", distance: "5.2 公里", traffic: "交通暢順", selected: true },
                { name: "替代路線", time: "18 分鐘", distance: "4.8 公里", traffic: "部分壅塞" },
                { name: "避開收費路段", time: "22 分鐘", distance: "6.1 公里", traffic: "交通暢順" },
              ].map((route, index) => (
                <button
                  key={index}
                  className={cn(
                    "w-full flex items-center gap-3 p-3 rounded-xl transition-colors text-left shadow-sm",
                    route.selected ? "bg-primary/10 border-2 border-primary" : "bg-card hover:bg-muted border border-border"
                  )}
                >
                  <div className="flex-1">
                    <p className="font-medium text-foreground">{route.name}</p>
                    <p className="text-sm text-muted-foreground">
                      {route.time} · {route.distance}
                    </p>
                  </div>
                  <span className={cn("text-xs", route.traffic === "交通暢順" ? "text-primary" : "text-yellow-500")}>
                    {route.traffic}
                  </span>
                </button>
              ))}
            </div>

            {/* Start Navigation Button */}
            <Button
              onClick={onStartNavigation}
              className="w-full h-14 bg-primary hover:bg-primary/90 text-primary-foreground rounded-2xl font-medium text-lg"
            >
              <Navigation className="w-5 h-5 mr-2" />
              開始導航
            </Button>
          </div>
        )}
      </div>

      {/* Footer Navigation */}
      <div className="p-4 border-t border-sidebar-border">
        <div className="flex justify-around">
          {[
            { icon: MapPin, label: "探索", view: "main" as SidebarView },
            { icon: Clock, label: "近期", view: "search" as SidebarView },
            { icon: Navigation, label: "導航", view: "navigation" as SidebarView },
            { icon: Settings, label: "設定", view: "settings" as SidebarView },
          ].map((item) => (
            <button
              key={item.label}
              onClick={() => setView(item.view)}
              className={cn(
                "flex flex-col items-center gap-1 p-2 rounded-lg transition-colors",
                view === item.view ? "text-primary" : "text-muted-foreground hover:text-foreground"
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
