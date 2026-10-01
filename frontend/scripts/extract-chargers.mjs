import fs from "fs"
import path from "path"
import { fileURLToPath } from "url"

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const csvPath = path.join(__dirname, "../lib/ChargePointData2011-2020-ManullyPreCleaned3.csv")
const text = fs.readFileSync(csvPath, "utf8")
const lines = text.split(/\r?\n/)
const header = lines[0].split(",")

const idx = {
  name: header.indexOf("Station Name"),
  lat: header.indexOf("Latitude"),
  lng: header.indexOf("Longitude"),
  fee: header.indexOf("Fee"),
  addr: header.indexOf("Address 1"),
  city: header.indexOf("City"),
  state: header.indexOf("State/Province"),
  port: header.indexOf("Port Type"),
}

function parseCsvLine(line) {
  const cols = []
  let cur = ""
  let inQ = false
  for (let i = 0; i < line.length; i++) {
    const c = line[i]
    if (c === '"') {
      inQ = !inQ
      continue
    }
    if (c === "," && !inQ) {
      cols.push(cur)
      cur = ""
      continue
    }
    cur += c
  }
  cols.push(cur)
  return cols
}

const seen = new Set()
const out = []

for (let i = 1; i < lines.length && out.length < 50; i++) {
  const line = lines[i]
  if (!line.trim()) continue
  const cols = parseCsvLine(line)
  const name = (cols[idx.name] || "").trim()
  const lat = parseFloat(cols[idx.lat])
  const lng = parseFloat(cols[idx.lng])
  const feeRaw = (cols[idx.fee] || "").trim()
  const fee = feeRaw === "" ? 0 : parseFloat(feeRaw)
  const addr1 = (cols[idx.addr] || "").trim()
  const city = (cols[idx.city] || "").trim()
  const state = (cols[idx.state] || "").trim()
  const port = (cols[idx.port] || "").trim()

  if (!name || Number.isNaN(lat) || Number.isNaN(lng)) continue
  const key = `${name}|${lat}|${lng}`
  if (seen.has(key)) continue
  seen.add(key)

  const chargerType = port.toLowerCase().includes("dc") ? "DC" : "AC"
  out.push({
    name,
    lat,
    lng,
    fee: Number.isNaN(fee) ? 0 : fee,
    address: [addr1, city, state].filter(Boolean).join(", "),
    port,
    chargerType,
  })
}

const outPath = path.join(__dirname, "../lib/csv-chargers.generated.ts")
const body = `/** Auto-generated from ChargePoint CSV — do not edit by hand */

export type CsvChargerPowerType = "DC" | "AC"

export interface CsvChargerRecord {
  name: string
  lat: number
  lng: number
  fee: number
  address: string
  port: string
  chargerType: CsvChargerPowerType
}

export const csvChargerRecords: CsvChargerRecord[] = ${JSON.stringify(out, null, 2)}

export const CSV_MAP_BOUNDS = {
  north: ${Math.max(...out.map((s) => s.lat)) + 0.05},
  south: ${Math.min(...out.map((s) => s.lat)) - 0.05},
  east: ${Math.max(...out.map((s) => s.lng)) + 0.05},
  west: ${Math.min(...out.map((s) => s.lng)) - 0.05},
}
`

fs.writeFileSync(outPath, body, "utf8")
console.log(`Wrote ${out.length} stations to ${outPath}`)
