"use client"

import { Compass, Clock, Navigation, Settings } from "lucide-react"

export type TabType = "explore" | "recent" | "go" | "settings"

interface BottomNavigationProps {
  activeTab: TabType
  onTabChange: (tab: TabType) => void
}

const tabs = [
  { id: "explore" as TabType, label: "Explore", icon: Compass },
  { id: "recent" as TabType, label: "Recent", icon: Clock },
  { id: "go" as TabType, label: "Go", icon: Navigation },
  { id: "settings" as TabType, label: "Settings", icon: Settings },
]

export function BottomNavigation({ activeTab, onTabChange }: BottomNavigationProps) {
  return (
    <div className="flex items-center justify-around py-3 px-4 bg-card border-t border-border">
      {tabs.map((tab) => {
        const isActive = activeTab === tab.id
        return (
          <button
            key={tab.id}
            onClick={() => onTabChange(tab.id)}
            className={`flex flex-col items-center gap-1 px-4 py-2 rounded-xl transition-colors ${
              isActive ? "text-primary" : "text-muted-foreground"
            }`}
          >
            <tab.icon className={`w-6 h-6 ${isActive ? "text-primary" : ""}`} />
            <span className="text-xs font-medium">{tab.label}</span>
          </button>
        )
      })}
    </div>
  )
}
