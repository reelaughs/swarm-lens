export type AppRoute =
  | { kind: "home" }
  | { kind: "episode"; slug: string }
  | { kind: "turningPoint"; slug: string; rank: number | null; rankSegment: string }
  | { kind: "notFound" };

function decodeSegment(value: string): string | null {
  try {
    return decodeURIComponent(value);
  } catch {
    return null;
  }
}

export function parseRoute(pathname: string): AppRoute {
  const segments = pathname.split("/").filter(Boolean);
  if (segments.length === 0) return { kind: "home" };
  if (segments[0] !== "episodes") return { kind: "notFound" };

  const slug = segments[1] ? decodeSegment(segments[1]) : null;
  if (!slug) return { kind: "notFound" };
  if (segments.length === 2) return { kind: "episode", slug };

  if (segments.length === 4 && segments[2] === "turning-points") {
    const rankSegment = decodeSegment(segments[3]);
    if (rankSegment === null) return { kind: "notFound" };
    const rank = /^\d+$/.test(rankSegment) ? Number(rankSegment) : null;
    return { kind: "turningPoint", slug, rank, rankSegment };
  }

  return { kind: "notFound" };
}

export function episodePath(slug: string): string {
  return `/episodes/${encodeURIComponent(slug)}`;
}

export function turningPointPath(slug: string, rank: number): string {
  return `${episodePath(slug)}/turning-points/${rank}`;
}
