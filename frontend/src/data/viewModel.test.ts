import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { validateEpisode, validateEpisodeCatalog } from "./loadEpisode";
import type { EpisodeCatalog, EpisodeViewModel } from "./types";

function catalogFixture(): EpisodeCatalog {
  const path = resolve(process.cwd(), "public/data/episodes.json");
  const value: unknown = JSON.parse(readFileSync(path, "utf8"));
  validateEpisodeCatalog(value);
  return value;
}

function fixture(): EpisodeViewModel {
  const path = resolve(process.cwd(), "public/data/perform-novel-research.json");
  const value: unknown = JSON.parse(readFileSync(path, "utf8"));
  const entry = catalogFixture().episodes[0];
  validateEpisode(value, entry);
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

  it("cross-checks catalog metadata against the generated view model", () => {
    const data = fixture();
    const entry = {
      ...catalogFixture().episodes[0],
      slug: "different-episode",
      title: "Mismatched title",
      start: "2026-01-01T00:00:00.000000+00:00",
      end: "2026-01-02T00:00:00.000000+00:00",
      turningPointCount: 4,
    };
    expect(() => validateEpisode(data, entry)).toThrow(
      /Catalog\/view-model mismatch.*slug.*title.*start timestamp.*end timestamp.*turning-point count/,
    );
  });

  it("rejects non-contiguous or out-of-order behavioral-change ranks", () => {
    const data = structuredClone(fixture());
    data.turningPoints[1].rank = 3;
    expect(() => validateEpisode(data)).toThrow(
      /Behavioral-change ranks must be unique, contiguous positive integers in ascending order/,
    );
  });

  it("rejects duplicate catalog slugs", () => {
    const catalog = catalogFixture();
    const duplicate = { ...catalog, episodes: [...catalog.episodes, { ...catalog.episodes[0] }] };
    expect(() => validateEpisodeCatalog(duplicate)).toThrow(/duplicate slug/);
  });
});
