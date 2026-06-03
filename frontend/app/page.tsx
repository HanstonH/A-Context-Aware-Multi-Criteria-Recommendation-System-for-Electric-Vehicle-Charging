"use client"

import { useState, useEffect } from "react"
import { LoginScreen } from "@/components/screens/login-screen"
import { Sidebar } from "@/components/sidebar"
import { MapView } from "@/components/map-view"

export default function MapExplorePage() {
  const [isLoggedIn, setIsLoggedIn] = useState(false)
  const [selectedDestination, setSelectedDestination] = useState<string | null>(null)
  const [isNavigating, setIsNavigating] = useState(false)
  const [darkMode, setDarkMode] = useState(false)

  // Apply dark mode class to html element
  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add("dark")
    } else {
      document.documentElement.classList.remove("dark")
    }
  }, [darkMode])

  const handleLogin = () => {
    setIsLoggedIn(true)
  }

  const handleLogout = () => {
    setIsLoggedIn(false)
    setSelectedDestination(null)
    setIsNavigating(false)
  }

  const handleNavigate = (destination: string) => {
    setSelectedDestination(destination)
    setIsNavigating(false)
  }

  const handleStartNavigation = () => {
    setIsNavigating(true)
  }

  const handleCancelNavigation = () => {
    setSelectedDestination(null)
    setIsNavigating(false)
  }

  // Render login screen
  if (!isLoggedIn) {
    return <LoginScreen onLogin={handleLogin} onRegister={() => {}} />
  }

  // Render main app with Google Maps-like layout
  return (
    <div className="h-screen w-full flex overflow-hidden">
      {/* Left Sidebar */}
      <Sidebar
        onNavigate={handleNavigate}
        onLogout={handleLogout}
        selectedDestination={selectedDestination}
        isNavigating={isNavigating}
        onStartNavigation={handleStartNavigation}
        onCancelNavigation={handleCancelNavigation}
        darkMode={darkMode}
        onDarkModeChange={setDarkMode}
      />

      {/* Map Area */}
      <div className="flex-1 relative">
        <MapView
          selectedDestination={selectedDestination}
          isNavigating={isNavigating}
          onClose={handleCancelNavigation}
        />
      </div>
    </div>
  )
}
