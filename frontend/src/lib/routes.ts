export type AppRoute =
  | { kind: "home" }
  | { kind: "dataset"; datasetId: string }
  | { kind: "run"; runId: string }
  | { kind: "episode"; slug: string }
  | { kind: "turningPoint"; slug: string; rank: number | null; rankSegment: string }
  | { kind: "runtimeEpisode"; runId: string; slug: string }
  | { kind: "runtimeTurningPoint"; runId: string; slug: string; rank: number | null; rankSegment: string }
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
  if (segments[0] === "datasets" && segments.length === 2) {
    const datasetId = decodeSegment(segments[1]);
    return datasetId ? { kind: "dataset", datasetId } : { kind: "notFound" };
  }
  if (segments[0] === "runs") {
    const runId = segments[1] ? decodeSegment(segments[1]) : null;
    if (!runId) return { kind: "notFound" };
    if (segments.length === 2) return { kind: "run", runId };
    if (segments.length === 4 && segments[2] === "episodes") {
      const slug = decodeSegment(segments[3]);
      return slug ? { kind: "runtimeEpisode", runId, slug } : { kind: "notFound" };
    }
    if (segments.length === 6 && segments[2] === "episodes" && segments[4] === "turning-points") {
      const slug = decodeSegment(segments[3]);
      const rankSegment = decodeSegment(segments[5]);
      if (!slug || rankSegment === null) return { kind: "notFound" };
      const rank = /^\d+$/.test(rankSegment) ? Number(rankSegment) : null;
      return { kind: "runtimeTurningPoint", runId, slug, rank, rankSegment };
    }
    return { kind: "notFound" };
  }
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

export function datasetPath(datasetId: string): string {
  return `/datasets/${encodeURIComponent(datasetId)}`;
}

export function runPath(runId: string): string {
  return `/runs/${encodeURIComponent(runId)}`;
}

export function runtimeEpisodePath(runId: string, slug: string): string {
  return `${runPath(runId)}/episodes/${encodeURIComponent(slug)}`;
}

export function runtimeTurningPointPath(runId: string, slug: string, rank: number): string {
  return `${runtimeEpisodePath(runId, slug)}/turning-points/${rank}`;
}
