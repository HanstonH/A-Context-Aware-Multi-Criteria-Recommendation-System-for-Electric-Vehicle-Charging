import type { GeoPoint } from "@/lib/map-coords"

/** 台灣全區視角（定位失敗時的預設地圖，不是虛擬定位座標） */
export const TAIWAN_CENTER: GeoPoint = {
  lat: 23.7,
  lng: 121.0,
}

export const TAIWAN_DEFAULT_ZOOM = 7

export const TAIWAN_BOUNDS = {
  north: 25.35,
  south: 21.85,
  east: 122.05,
  west: 119.3,
}

/** 以 GPS 為中心的周遭充電站搜尋半徑 */
export const NEARBY_SEARCH_RADIUS_KM = 15

export const NEARBY_MAP_ZOOM = 13
