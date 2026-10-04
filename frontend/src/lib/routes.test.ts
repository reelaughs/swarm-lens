import { describe, expect, it } from "vitest";
import { episodePath, parseRoute, runtimeEpisodePath, runtimeTurningPointPath, turningPointPath } from "./routes";

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

  it("parses runtime investigations without changing frozen example routes", () => {
    expect(parseRoute("/runs/run_123/episodes/runtime-episode")).toEqual({
      kind: "runtimeEpisode",
      runId: "run_123",
      slug: "runtime-episode",
    });
    expect(parseRoute("/runs/run_123/episodes/runtime-episode/turning-points/2")).toEqual({
      kind: "runtimeTurningPoint",
      runId: "run_123",
      slug: "runtime-episode",
      rank: 2,
      rankSegment: "2",
    });
    expect(runtimeEpisodePath("run_123", "runtime-episode")).toBe(
      "/runs/run_123/episodes/runtime-episode",
    );
    expect(runtimeTurningPointPath("run_123", "runtime-episode", 2)).toBe(
      "/runs/run_123/episodes/runtime-episode/turning-points/2",
    );
    expect(episodePath("perform-novel-research")).toBe("/episodes/perform-novel-research");
  });
});
