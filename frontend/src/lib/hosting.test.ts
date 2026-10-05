import { describe, expect, it } from "vitest";
import { browserRouteHref, routePathFromLocation } from "./hosting";

describe("hosted-demo routing", () => {
  it("reads logical routes from the hash in hosted mode", () => {
    expect(routePathFromLocation(
      { pathname: "/swarm-lens/", hash: "#/episodes/perform-novel-research/turning-points/2" },
      true,
    )).toBe("/episodes/perform-novel-research/turning-points/2");
    expect(routePathFromLocation({ pathname: "/swarm-lens/", hash: "" }, true)).toBe("/");
  });

  it("keeps History API paths in local mode", () => {
    expect(routePathFromLocation(
      { pathname: "/episodes/perform-novel-research", hash: "#/ignored" },
      false,
    )).toBe("/episodes/perform-novel-research");
  });

  it("builds repository-subpath-safe hosted links", () => {
    expect(browserRouteHref("/episodes/perform-novel-research", true, "/swarm-lens/")).toBe(
      "/swarm-lens/#/episodes/perform-novel-research",
    );
    expect(browserRouteHref("/episodes/perform-novel-research", false, "/")).toBe(
      "/episodes/perform-novel-research",
    );
  });
});
