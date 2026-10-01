import { NextResponse } from "next/server"
import { fetchExpressStationsRaw } from "@/lib/api/backend-proxy"
import { mapApiStationsToLocations } from "@/lib/api/normalize"
import { ApiError } from "@/lib/api/http"

export async function GET() {
  try {
    const { data, path } = await fetchExpressStationsRaw()
    const locations = mapApiStationsToLocations(data)

    if (locations.length === 0) {
      return NextResponse.json(
        {
          error: `Express 已回應（${path}），但沒有可顯示的充電站。請確認回傳為陣列，且含 "Station Name" 與 "Latitude"/"Longitude"。`,
          path,
        },
        { status: 502 }
      )
    }

    return NextResponse.json({
      source: "express",
      path,
      count: locations.length,
      locations,
    })
  } catch (error) {
    const message = error instanceof Error ? error.message : "讀取充電站失敗"
    const status = error instanceof ApiError && error.status >= 400 ? error.status : 502
    return NextResponse.json({ error: message }, { status })
  }
}
