import { describe, expect, it } from "vitest";
import { largestDirectionalChanges, percentagePointDelta } from "./DetectorShifts";

describe("largestDirectionalChanges", () => {
  it("selects the largest increase and decrease without using absolute value for direction", () => {
    const result = largestDirectionalChanges([
      { label: "C01: one", before: 0.1, after: 0.2, delta: 0.1 },
      { label: "C02: two", before: 0.3, after: 0.05, delta: -0.25 },
      { label: "C03: three", before: 0.1, after: 0.25, delta: 0.15 },
      { label: "C04: four", before: 0.2, after: 0.1, delta: -0.1 },
    ]);

    expect(result.increase?.label).toBe("C03: three");
    expect(result.decrease?.label).toBe("C02: two");
  });

  it("reports a missing direction instead of inventing a shift", () => {
    const result = largestDirectionalChanges([
      { label: "AGENT_TALK", before: 0.1, after: 0.2, delta: 0.1 },
    ]);

    expect(result.increase?.label).toBe("AGENT_TALK");
    expect(result.decrease).toBeNull();
  });

  it("formats normalized share differences as percentage points", () => {
    expect(percentagePointDelta(0.10718377292282578)).toBe("+10.7 pp");
    expect(percentagePointDelta(-0.08699315028833021)).toBe("−8.7 pp");
  });
});
