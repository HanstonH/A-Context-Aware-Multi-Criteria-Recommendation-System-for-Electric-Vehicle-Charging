"use client"

import { useState } from "react"
import {
  Menu,
  User,
  MapIcon,
  Download,
  Navigation,
  Moon,
  Bell,
  Info,
  ChevronRight,
  LogOut,
  MapPin,
} from "lucide-react"
import { Switch } from "@/components/ui/switch"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"

interface SettingsScreenProps {
  onMenuClick: () => void
  onLogout: () => void
}

export function SettingsScreen({ onMenuClick, onLogout }: SettingsScreenProps) {
  const [darkMode, setDarkMode] = useState(true)
  const [trafficAlerts, setTrafficAlerts] = useState(true)

  const menuItems = [
    {
      icon: User,
      label: "個人資料",
      description: "管理您的帳戶與隱私設定",
      hasChevron: true,
    },
    {
      icon: MapIcon,
      label: "地圖設定",
      hasChevron: true,
    },
    {
      icon: Download,
      label: "離線地圖",
      description: "3 個已下載",
      hasChevron: true,
    },
    {
      icon: Navigation,
      label: "導航設定",
      hasChevron: true,
    },
  ]

  return (
    <div className="h-full flex flex-col bg-background">
      {/* Header */}
      <div className="p-4 flex items-center gap-3 border-b border-border">
        <button
          onClick={onMenuClick}
          className="w-10 h-10 rounded-full bg-card flex items-center justify-center text-foreground"
        >
          <Menu className="w-5 h-5" />
        </button>
        <div className="flex-1 flex items-center gap-2">
          <MapPin className="w-5 h-5 text-primary" />
          <span className="font-semibold text-foreground">MapExplore</span>
        </div>
        <Avatar className="w-10 h-10 border-2 border-primary">
          <AvatarImage src="/placeholder.svg" alt="使用者頭像" />
          <AvatarFallback className="bg-primary text-primary-foreground">ME</AvatarFallback>
        </Avatar>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        <h1 className="text-lg font-semibold text-foreground mb-4">設定</h1>

        {/* Menu Items */}
        <div className="space-y-2 mb-6">
          {menuItems.map((item) => (
            <button
              key={item.label}
              className="w-full flex items-center gap-3 p-4 bg-card rounded-xl hover:bg-card/80 transition-colors"
            >
              <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center">
                <item.icon className="w-5 h-5 text-foreground" />
              </div>
              <div className="flex-1 text-left">
                <p className="font-medium text-foreground">{item.label}</p>
                {item.description && (
                  <p className="text-sm text-primary">{item.description}</p>
                )}
              </div>
              {item.hasChevron && <ChevronRight className="w-5 h-5 text-muted-foreground" />}
            </button>
          ))}
        </div>

        {/* Toggle Settings */}
        <div className="space-y-2 mb-6">
          <div className="flex items-center justify-between p-4 bg-card rounded-xl">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center">
                <Moon className="w-5 h-5 text-foreground" />
              </div>
              <span className="font-medium text-foreground">深色模式</span>
            </div>
            <Switch checked={darkMode} onCheckedChange={setDarkMode} />
          </div>

          <div className="flex items-center justify-between p-4 bg-card rounded-xl">
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
        <div className="mb-6">
          <button className="w-full flex items-center gap-3 p-4 bg-card rounded-xl hover:bg-card/80 transition-colors">
            <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center">
              <Info className="w-5 h-5 text-foreground" />
            </div>
            <div className="flex-1 text-left">
              <p className="font-medium text-foreground">關於</p>
              <p className="text-sm text-muted-foreground">v 2.4.1 (Build 882)</p>
            </div>
            <ChevronRight className="w-5 h-5 text-muted-foreground" />
          </button>
        </div>

        {/* Logout Button */}
        <button
          onClick={onLogout}
          className="w-full flex items-center justify-center gap-2 p-4 bg-card rounded-xl text-destructive hover:bg-destructive/10 transition-colors"
        >
          <LogOut className="w-5 h-5" />
          <span className="font-medium">登出帳號</span>
        </button>
      </div>
    </div>
  )
}
