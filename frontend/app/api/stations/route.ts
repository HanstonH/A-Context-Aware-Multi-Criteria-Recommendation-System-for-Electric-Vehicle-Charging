import { NextResponse } from "next/server"
import { clientIpFrom, fetchBackendStationsRaw } from "@/lib/api/backend-proxy"
import { mapApiStationsToLocations } from "@/lib/api/normalize"
import { ApiError } from "@/lib/api/http"

export async function GET(request: Request) {
  try {
    const { data, path } = await fetchBackendStationsRaw(clientIpFrom(request))
    const locations = mapApiStationsToLocations(data)

    if (locations.length === 0) {
      return NextResponse.json(
        {
          error: `後端已回應（${path}），但沒有可顯示的充電站。`,
          path,
        },
        { status: 502 }
      )
    }

    return NextResponse.json({
      source: "backend",
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
