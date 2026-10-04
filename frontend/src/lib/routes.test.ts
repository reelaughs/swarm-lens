import { describe, expect, it } from "vitest";
import { episodePath, parseRoute, turningPointPath } from "./routes";

describe("application routes", () => {
  it("parses home, episode, and turning-point paths", () => {
    expect(parseRoute("/")).toEqual({ kind: "home" });
    expect(parseRoute("/episodes/perform-novel-research")).toEqual({
      kind: "episode",
      slug: "perform-novel-research",
    });
    expect(parseRoute("/episodes/perform-novel-research/turning-points/4")).toEqual({
      kind: "turningPoint",
      slug: "perform-novel-research",
      rank: 4,
      rankSegment: "4",
    });
  });

  it("preserves an invalid rank as an explicit turning-point route", () => {
    expect(parseRoute("/episodes/perform-novel-research/turning-points/nope")).toEqual({
      kind: "turningPoint",
      slug: "perform-novel-research",
      rank: null,
      rankSegment: "nope",
    });
    expect(parseRoute("/episodes/perform-novel-research/turning-points/0")).toEqual({
      kind: "turningPoint",
      slug: "perform-novel-research",
      rank: 0,
      rankSegment: "0",
    });
  });

  it("rejects unrelated or incomplete paths", () => {
    expect(parseRoute("/unknown")).toEqual({ kind: "notFound" });
    expect(parseRoute("/episodes")).toEqual({ kind: "notFound" });
    expect(parseRoute("/episodes/example/extra")).toEqual({ kind: "notFound" });
  });

  it("builds stable episode URLs", () => {
    expect(episodePath("perform-novel-research")).toBe("/episodes/perform-novel-research");
    expect(turningPointPath("perform-novel-research", 2)).toBe(
      "/episodes/perform-novel-research/turning-points/2",
    );
  });
});
