import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { validateEpisode } from "./loadEpisode";
import type { EpisodeViewModel } from "./types";

function fixture(): EpisodeViewModel {
  const path = resolve(process.cwd(), "public/data/perform-novel-research.json");
  const value: unknown = JSON.parse(readFileSync(path, "utf8"));
  validateEpisode(value);
  return value;
}

describe("frozen episode view model", () => {
  it("preserves Stage 2 rank order and all Stage 2.5 observations", () => {
    const data = fixture();
    expect(data.turningPoints.map((point) => point.rank)).toEqual([1, 2, 3, 4, 5]);
    expect(data.turningPoints.every((point) => point.deterministicDescriptions.length === 4)).toBe(true);
    expect(data.turningPoints.every((point) => !("strongestDeterministicDescription" in point))).toBe(true);
  });

  it("keeps detector scores separate from interpretation confidence", () => {
    const data = fixture();
    for (const point of data.turningPoints) {
      expect(typeof point.aggregateDetectorScore).toBe("number");
      for (const hypothesis of point.interpretation.socialProcessEvaluation.hypotheses) {
        expect(["low", "moderate", "high"]).toContain(hypothesis.displayed_confidence);
        expect(["low", "moderate", "high"]).toContain(hypothesis.evidence_diversity);
      }
    }
  });

  it("preserves every Stage 4 evidence reference with provenance", () => {
    const data = fixture();
    for (const point of data.turningPoints) {
      expect(point.referencedEvidence.length).toBeGreaterThan(0);
      expect(point.referencedEvidence.every((item) => Boolean(item.evidenceId))).toBe(true);
      expect(point.referencedEvidence.every((item) => Boolean(item.provenance))).toBe(true);
    }
  });
});
