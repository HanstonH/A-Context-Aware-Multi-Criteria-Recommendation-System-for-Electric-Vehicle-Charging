/** 隱藏 Google 地圖原生 POI（地標／店家圖示），只保留我們自己畫的 Marker */
export const HIDE_NATIVE_POI_STYLES: google.maps.MapTypeStyle[] = [
  {
    featureType: "poi",
    elementType: "labels",
    stylers: [{ visibility: "off" }],
  },
  {
    featureType: "poi",
    elementType: "geometry",
    stylers: [{ visibility: "off" }],
  },
]
