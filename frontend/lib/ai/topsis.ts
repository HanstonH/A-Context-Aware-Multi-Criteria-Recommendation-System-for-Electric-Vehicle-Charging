import { getExponentialWeights } from "@/lib/ai/weights"

const IS_COST_CRITERION = [true, false, true, false]
const OCCUPIED_PENALTY = 1e9

export interface TopsisCandidate {
  id: string
  distance: number
  poiCount: number
  cost: number
  availablePots: number
}

export interface TopsisScored<T extends TopsisCandidate> extends T {
  topsisScore: number
}

export function topsisRank<T extends TopsisCandidate>(
  stations: T[],
  batteryFraction: number,
  isAvailableNow: boolean
): TopsisScored<T>[] {
  if (stations.length === 0) return []

  const weights = getExponentialWeights(batteryFraction, isAvailableNow)
  const w = [weights.wDistance, weights.wPoi, weights.wCost, weights.wPots]

  const working = stations.map((station) => {
    const distance =
      isAvailableNow && station.availablePots === 0
        ? station.distance + OCCUPIED_PENALTY
        : station.distance
    return [
      distance,
      station.poiCount,
      station.cost,
      station.availablePots,
    ]
  })

  const colNorms = [0, 0, 0, 0]
  for (const row of working) {
    for (let j = 0; j < 4; j += 1) colNorms[j] += row[j] * row[j]
  }
  for (let j = 0; j < 4; j += 1) colNorms[j] = Math.sqrt(colNorms[j]) || 1

  const V = working.map((row) => row.map((value, j) => (value / colNorms[j]) * w[j]))

  const PIS = [0, 0, 0, 0]
  const NIS = [0, 0, 0, 0]
  for (let j = 0; j < 4; j += 1) {
    const col = V.map((row) => row[j])
    const min = Math.min(...col)
    const max = Math.max(...col)
    PIS[j] = IS_COST_CRITERION[j] ? min : max
    NIS[j] = IS_COST_CRITERION[j] ? max : min
  }

  const scores = V.map((row) => {
    let sPos = 0
    let sNeg = 0
    for (let j = 0; j < 4; j += 1) {
      sPos += (row[j] - PIS[j]) ** 2
      sNeg += (row[j] - NIS[j]) ** 2
    }
    sPos = Math.sqrt(sPos)
    sNeg = Math.sqrt(sNeg)
    const denom = sPos + sNeg
    return denom === 0 ? 0.5 : sNeg / denom
  })

  return stations
    .map((station, index) => ({
      ...station,
      topsisScore: Math.round(scores[index] * 1e6) / 1e6,
    }))
    .sort((a, b) => b.topsisScore - a.topsisScore)
}
