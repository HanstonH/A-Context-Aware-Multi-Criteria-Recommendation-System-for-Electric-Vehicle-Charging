import { describe, expect, it } from "vitest"
import { contextStateLabel, getExponentialWeights } from "@/lib/ai/weights"

const sum = (w: ReturnType<typeof getExponentialWeights>) => w.wDistance + w.wPoi + w.wCost + w.wPots

describe("getExponentialWeights", () => {
  it.each([0, 0.1, 0.25, 0.5, 0.75, 1])("sums to 1 at battery %s", (battery) => {
    expect(sum(getExponentialWeights(battery, false))).toBeCloseTo(1, 10)
  })

  it("uses the fixed urgency vector when the user needs a slot now", () => {
    expect(getExponentialWeights(0.9, true)).toEqual({ wDistance: 0.55, wPoi: 0.05, wCost: 0.05, wPots: 0.35 })
  })

  it("favours distance at low battery and cost at high battery", () => {
    const low = getExponentialWeights(0.05, false)
    const high = getExponentialWeights(0.95, false)
    expect(low.wDistance).toBeGreaterThan(low.wCost)
    expect(high.wCost).toBeGreaterThan(high.wDistance)
    expect(low.wDistance).toBeGreaterThan(high.wDistance)
  })

  it("clamps out-of-range battery values", () => {
    expect(getExponentialWeights(-1, false)).toEqual(getExponentialWeights(0, false))
    expect(getExponentialWeights(2, false)).toEqual(getExponentialWeights(1, false))
  })
})

describe("contextStateLabel", () => {
  it.each([
    [0.1, false, "LOW BATTERY"],
    [0.2, false, "MID BATTERY"],
    [0.5, false, "HIGH BATTERY"],
    [0.1, true, "URGENT"],
  ])("battery %s urgent=%s -> %s", (battery, urgent, label) => {
    expect(contextStateLabel(battery, urgent)).toBe(label)
  })
})
