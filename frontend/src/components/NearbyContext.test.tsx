import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { validateEpisode } from "../data/loadEpisode";
import type { EpisodeViewModel } from "../data/types";
import { NearbyContext, nearbyContextItems } from "./NearbyContext";

function fixture(): EpisodeViewModel {
  const value: unknown = JSON.parse(
    readFileSync(
      resolve(process.cwd(), "public/data/connect-your-worlds-into-a-3d-universe.json"),
      "utf8",
    ),
  );
  validateEpisode(value);
  return value;
}

describe("Nearby context", () => {
  it("surfaces the human repair-prioritization message for turning point 4", () => {
    const point = fixture().turningPoints.find((item) => item.rank === 4)!;
    const items = nearbyContextItems(point);
    const message = items.find((item) => item.actor === "Shoshannah")!;

    expect(message.eventType).toBe("Human / administrator message");
    expect(message.relativeTiming).toBe("59 min before");
    expect(message.text).toBe(
      "Hi guys, today is the last day of your current goal and the universe view seems broken. Please consider prioritizing fixing this together before expanding further. It's important to deliver something functional at the end of the day. Good luck!",
    );

    const markup = renderToStaticMarkup(<NearbyContext point={point} />);
    expect(markup).toContain("Nearby context");
    expect(markup).toContain("Human / administrator message");
    expect(markup).toContain("59 min before");
    expect(markup).toContain("Temporal proximity does not establish influence or causation");
    expect(markup).toContain("universe view seems broken");
  });

  it("renders nothing when no structured nearby context is available", () => {
    const point = structuredClone(fixture().turningPoints[0]);
    point.compactEvidence = point.compactEvidence.filter(
      (item) => !item.categories.includes("external_context"),
    );
    point.externalContextEvents = [];
    expect(renderToStaticMarkup(<NearbyContext point={point} />)).toBe("");
  });

  it("contains no episode-specific branch", () => {
    const source = readFileSync(resolve(process.cwd(), "src/components/NearbyContext.tsx"), "utf8");
    expect(source).not.toContain("connect-your-worlds");
    expect(source).not.toContain("perform-novel-research");
  });
});
