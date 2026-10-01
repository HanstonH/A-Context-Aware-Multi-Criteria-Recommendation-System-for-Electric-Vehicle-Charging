/** 對齊 `AI/Algorithm/logic.py` 的指數權重引擎 */

export interface WeightVector {
  wDistance: number
  wPoi: number
  wCost: number
  wPots: number
}

const W_BASE_DIST = 0.1
const W_SURVIVAL_AMP_DIST = 0.6
const W_BASE_POTS = 0.15
const W_SURVIVAL_AMP_POTS = 0.3
const K_SURVIVAL = 7
const W_MAX_COST = 0.4
const W_MAX_POI = 0.35
const K_COMFORT = 4
const URGENCY_WEIGHTS: [number, number, number, number] = [0.55, 0.05, 0.05, 0.35]

export function getExponentialWeights(
  batteryFraction: number,
  isAvailableNow: boolean
): WeightVector {
  if (isAvailableNow) {
    const [wDistance, wPoi, wCost, wPots] = URGENCY_WEIGHTS
    return { wDistance, wPoi, wCost, wPots }
  }

  const B = Math.min(1, Math.max(0, batteryFraction))
  const survivalDecay = Math.exp(-K_SURVIVAL * B)
  const comfortGrowth = 1 - Math.exp(-K_COMFORT * B)

  const raw = [
    W_BASE_DIST + W_SURVIVAL_AMP_DIST * survivalDecay,
    W_MAX_POI * comfortGrowth,
    W_MAX_COST * comfortGrowth,
    W_BASE_POTS + W_SURVIVAL_AMP_POTS * survivalDecay,
  ]
  const total = raw.reduce((sum, value) => sum + value, 0) || 1
  return {
    wDistance: raw[0] / total,
    wPoi: raw[1] / total,
    wCost: raw[2] / total,
    wPots: raw[3] / total,
  }
}

export function contextStateLabel(batteryFraction: number, isAvailableNow: boolean): string {
  if (isAvailableNow) return "URGENT"
  if (batteryFraction < 0.2) return "LOW BATTERY"
  if (batteryFraction < 0.5) return "MID BATTERY"
  return "HIGH BATTERY"
}
