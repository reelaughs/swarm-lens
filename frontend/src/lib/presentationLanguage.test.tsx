import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { EpisodeMapPage } from "../pages/EpisodeMapPage";
import { TurningPointPage } from "../pages/TurningPointPage";
import { EvidenceSequence } from "../components/EvidenceSequence";
import { validateEpisode } from "../data/loadEpisode";
import type { EpisodeViewModel } from "../data/types";
import {
  containsInternalStageTerm,
  investigatorText,
} from "./presentationLanguage";

const EPISODE_SLUGS = [
  "perform-novel-research",
  "connect-your-worlds-into-a-3d-universe",
];

function loadEpisode(slug: string): EpisodeViewModel {
  const path = resolve(process.cwd(), `public/data/${slug}.json`);
  const value: unknown = JSON.parse(readFileSync(path, "utf8"));
  validateEpisode(value);
  return value;
}

function collectStrings(value: unknown, result: string[] = []): string[] {
  if (typeof value === "string") result.push(value);
  else if (Array.isArray(value)) value.forEach((item) => collectStrings(item, result));
  else if (value && typeof value === "object") {
    Object.values(value).forEach((item) => collectStrings(item, result));
  }
  return result;
}

function generatedProductStrings(data: EpisodeViewModel): string[] {
  const generated = structuredClone(data);
  for (const point of generated.turningPoints) {
    point.compactEvidence = [];
    point.reconstruction.rankedPrecedingEvidence.forEach((item) => { item.text = null; });
    point.referencedEvidence.forEach((item) => { delete item.record.text; });
  }
  return collectStrings(generated);
}

describe("investigator-facing presentation language", () => {
  it("removes internal stage terminology when generated product language is translated", () => {
    for (const slug of EPISODE_SLUGS) {
      for (const value of generatedProductStrings(loadEpisode(slug))) {
        expect(containsInternalStageTerm(investigatorText(value))).toBe(false);
      }
    }
  });

  it("renders generated product language without internal stage terminology", () => {
    for (const slug of EPISODE_SLUGS) {
      const data = loadEpisode(slug);
      const mapMarkup = renderToStaticMarkup(
        <EpisodeMapPage data={data} onInvestigate={() => undefined} />,
      );
      expect(containsInternalStageTerm(mapMarkup)).toBe(false);

      for (const point of data.turningPoints) {
        const displayPoint = structuredClone(point);
        displayPoint.compactEvidence.forEach((item) => { item.text = "RAW SOURCE EVIDENCE"; });
        displayPoint.reconstruction.rankedPrecedingEvidence.forEach((item) => {
          item.text = "RAW SOURCE EVIDENCE";
        });
        displayPoint.reconstruction.structuralObservations = {};
        displayPoint.referencedEvidence.forEach((item) => {
          if ("text" in item.record) item.record.text = "RAW SOURCE EVIDENCE";
        });
        const detailMarkup = renderToStaticMarkup(
          <TurningPointPage data={data} point={displayPoint} onBack={() => undefined} />,
        );
        expect(containsInternalStageTerm(detailMarkup)).toBe(false);
        for (const internalPath of Object.values(point.sourcePaths)) {
          expect(detailMarkup).not.toContain(internalPath);
        }
      }
    }
  });

  it("renders raw source-record text verbatim, including source-authored stage wording", () => {
    const data = loadEpisode("perform-novel-research");
    const sourceRecord = data.turningPoints
      .flatMap((point) => point.compactEvidence)
      .find((item) => item.text && /\bstage\s*(?:1|2(?:\.5)?|3|4)\b/i.test(item.text));
    expect(sourceRecord?.text).toBeTruthy();
    const markup = renderToStaticMarkup(
      <EvidenceSequence evidence={[sourceRecord!]} boundary={data.turningPoints[0].timestamp} />,
    );
    const renderedSourceText = renderToStaticMarkup(<>{sourceRecord!.text}</>);
    expect(markup).toContain(renderedSourceText);
  });
});
