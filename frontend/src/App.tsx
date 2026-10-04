import { useEffect, useMemo, useState } from "react";
import { SiteHeader } from "./components/SiteHeader";
import { loadEpisode, loadEpisodeCatalog } from "./data/loadEpisode";
import { loadRuntimeEpisode } from "./data/api";
import type { EpisodeCatalog, EpisodeViewModel } from "./data/types";
import {
  datasetPath,
  episodePath,
  parseRoute,
  runPath,
  runtimeEpisodePath,
  runtimeTurningPointPath,
  turningPointPath,
  type AppRoute,
} from "./lib/routes";
import { DatasetPage } from "./pages/DatasetPage";
import { EpisodeMapPage } from "./pages/EpisodeMapPage";
import { HomePage } from "./pages/HomePage";
import { RunStatusPage } from "./pages/RunStatusPage";
import { TurningPointPage } from "./pages/TurningPointPage";

function StatePage({
  eyebrow,
  title,
  message,
  action,
}: {
  eyebrow: string;
  title: string;
  message: string;
  action?: { label: string; onClick: () => void };
}) {
  return (
    <main className="page-shell state-page">
      <div className="eyebrow">{eyebrow}</div>
      <h1>{title}</h1>
      <p>{message}</p>
      {action && <button className="outline-button" onClick={action.onClick}>{action.label}</button>}
    </main>
  );
}

export default function App() {
  const [route, setRoute] = useState<AppRoute>(() => parseRoute(window.location.pathname));
  const [catalog, setCatalog] = useState<EpisodeCatalog | null>(null);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [data, setData] = useState<EpisodeViewModel | null>(null);
  const [episodeError, setEpisodeError] = useState<string | null>(null);
  const [episodeLoading, setEpisodeLoading] = useState(false);
  const [runtimeData, setRuntimeData] = useState<EpisodeViewModel | null>(null);
  const [runtimeError, setRuntimeError] = useState<string | null>(null);
  const [runtimeLoading, setRuntimeLoading] = useState(false);

  useEffect(() => {
    let active = true;
    loadEpisodeCatalog()
      .then((value) => {
        if (active) setCatalog(value);
      })
      .catch((reason: unknown) => {
        if (active) setCatalogError(reason instanceof Error ? reason.message : "Could not load episode catalog.");
      });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    const onPopState = () => setRoute(parseRoute(window.location.pathname));
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const activeSlug = route.kind === "episode" || route.kind === "turningPoint" ? route.slug : null;
  const activeEntry = useMemo(
    () => activeSlug ? catalog?.episodes.find((entry) => entry.slug === activeSlug) ?? null : null,
    [activeSlug, catalog],
  );
  const invalidRequestedRank = route.kind === "turningPoint" && (
    route.rank === null
    || route.rank < 1
    || !Number.isInteger(route.rank)
    || Boolean(activeEntry && route.rank > activeEntry.turningPointCount)
  );

  useEffect(() => {
    let active = true;
    if (!catalog || !activeEntry || invalidRequestedRank) {
      setData(null);
      setEpisodeError(null);
      setEpisodeLoading(false);
      return () => { active = false; };
    }

    setData(null);
    setEpisodeError(null);
    setEpisodeLoading(true);
    loadEpisode(activeEntry)
      .then((value) => {
        if (active) setData(value);
      })
      .catch((reason: unknown) => {
        if (active) setEpisodeError(reason instanceof Error ? reason.message : "Could not load episode data.");
      })
      .finally(() => {
        if (active) setEpisodeLoading(false);
      });
    return () => { active = false; };
  }, [activeEntry, catalog, invalidRequestedRank]);

  const runtimeRoute = route.kind === "runtimeEpisode" || route.kind === "runtimeTurningPoint" ? route : null;
  useEffect(() => {
    let active = true;
    if (!runtimeRoute) {
      setRuntimeData(null);
      setRuntimeError(null);
      setRuntimeLoading(false);
      return () => { active = false; };
    }
    setRuntimeData(null);
    setRuntimeError(null);
    setRuntimeLoading(true);
    loadRuntimeEpisode(runtimeRoute.runId)
      .then((value) => {
        if (!active) return;
        if (value.episode.slug !== runtimeRoute.slug) {
          throw new Error("Runtime route/view-model episode mismatch.");
        }
        setRuntimeData(value);
      })
      .catch((reason: unknown) => {
        if (active) setRuntimeError(reason instanceof Error ? reason.message : "Could not load runtime investigation.");
      })
      .finally(() => { if (active) setRuntimeLoading(false); });
    return () => { active = false; };
  }, [runtimeRoute?.runId, runtimeRoute?.slug]);

  const navigate = (path: string) => {
    if (window.location.pathname !== path) window.history.pushState({}, "", path);
    setRoute(parseRoute(path));
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  let content;
  if (route.kind === "dataset") {
    content = <DatasetPage datasetId={route.datasetId} onRunCreated={(runId) => navigate(runPath(runId))} />;
  } else if (route.kind === "run") {
    content = (
      <RunStatusPage
        runId={route.runId}
        onOpen={(run) => navigate(runtimeEpisodePath(run.id, run.episode_slug))}
      />
    );
  } else if (runtimeRoute) {
    const invalidRuntimeRank = runtimeRoute.kind === "runtimeTurningPoint" && (
      runtimeRoute.rank === null || runtimeRoute.rank < 1 || !Number.isInteger(runtimeRoute.rank)
    );
    if (invalidRuntimeRank) {
      content = (
        <StatePage
          eyebrow="Invalid turning point"
          title="Turning point not found"
          message={`Turning-point rank “${runtimeRoute.rankSegment}” is not valid.`}
          action={{ label: "Return to run", onClick: () => navigate(runPath(runtimeRoute.runId)) }}
        />
      );
    } else if (runtimeError) {
      content = <StatePage eyebrow="Loading error" title="Investigation could not be loaded" message={runtimeError} action={{ label: "Return to run", onClick: () => navigate(runPath(runtimeRoute.runId)) }} />;
    } else if (runtimeLoading || !runtimeData) {
      content = <main className="state-message"><p>Loading runtime investigation…</p></main>;
    } else if (runtimeRoute.kind === "runtimeTurningPoint") {
      const point = runtimeData.turningPoints.find((value) => value.rank === runtimeRoute.rank);
      content = point ? (
        <TurningPointPage
          data={runtimeData}
          point={point}
          onBack={() => navigate(runtimeEpisodePath(runtimeRoute.runId, runtimeData.episode.slug))}
        />
      ) : (
        <StatePage eyebrow="Invalid turning point" title="Turning point not found" message={`Turning-point rank “${runtimeRoute.rankSegment}” is not available for ${runtimeData.episode.goalText}.`} action={{ label: "Return to episode map", onClick: () => navigate(runtimeEpisodePath(runtimeRoute.runId, runtimeData.episode.slug)) }} />
      );
    } else {
      content = (
        <EpisodeMapPage
          data={runtimeData}
          onInvestigate={(rank) => navigate(runtimeTurningPointPath(runtimeRoute.runId, runtimeData.episode.slug, rank))}
        />
      );
    }
  } else if (catalogError) {
    content = <StatePage eyebrow="Catalog error" title="Investigations unavailable" message={catalogError} />;
  } else if (!catalog) {
    content = <main className="state-message"><p>Loading investigation catalog…</p></main>;
  } else if (route.kind === "notFound") {
    content = (
      <StatePage
        eyebrow="Route not found"
        title="Page not found"
        message="This SwarmLens route is not available."
        action={{ label: "Return home", onClick: () => navigate("/") }}
      />
    );
  } else if (route.kind === "home") {
    content = (
      <HomePage
        episodes={catalog.episodes}
        onOpenEpisode={(slug) => navigate(episodePath(slug))}
        onDatasetCreated={(datasetId) => navigate(datasetPath(datasetId))}
      />
    );
  } else if (!activeEntry) {
    content = (
      <StatePage
        eyebrow="Unknown episode"
        title="Episode not found"
        message={`No precomputed episode is registered for “${activeSlug}”.`}
        action={{ label: "Explore available investigations", onClick: () => navigate("/") }}
      />
    );
  } else if (invalidRequestedRank) {
    const rankLabel = route.kind === "turningPoint" ? route.rankSegment : "unknown";
    content = (
      <StatePage
        eyebrow="Invalid turning point"
        title="Turning point not found"
        message={`Turning-point rank “${rankLabel}” is not available for ${activeEntry.title}`}
        action={{ label: "Return to episode map", onClick: () => navigate(episodePath(activeEntry.slug)) }}
      />
    );
  } else if (episodeError) {
    const validationFailure = episodeError.startsWith("Catalog/view-model mismatch");
    content = (
      <StatePage
        eyebrow={validationFailure ? "Validation error" : "Loading error"}
        title={validationFailure ? "Episode validation failed" : "Episode could not be loaded"}
        message={episodeError}
        action={{ label: "Return home", onClick: () => navigate("/") }}
      />
    );
  } else if (episodeLoading || !data) {
    content = <main className="state-message"><p>Loading frozen episode…</p></main>;
  } else if (route.kind === "turningPoint") {
    const point = data.turningPoints.find((value) => value.rank === route.rank);
    content = point ? (
      <TurningPointPage
        data={data}
        point={point}
        onBack={() => navigate(episodePath(data.episode.slug))}
      />
    ) : (
      <StatePage
        eyebrow="Invalid turning point"
        title="Turning point not found"
        message={`Turning-point rank “${route.rankSegment}” is not available for ${data.episode.goalText}`}
        action={{ label: "Return to episode map", onClick: () => navigate(episodePath(data.episode.slug)) }}
      />
    );
  } else {
    content = (
      <EpisodeMapPage
        data={data}
        onInvestigate={(rank) => navigate(turningPointPath(data.episode.slug, rank))}
      />
    );
  }

  return (
    <div className="app-shell">
      <SiteHeader
        label={
          runtimeData?.presentation.label
          ?? (data && data.episode.slug === activeSlug ? data.presentation.label : undefined)
        }
        onHome={() => navigate("/")}
      />
      {content}
      <footer className="site-footer">
        <span>SwarmLens</span>
        <span>Frozen behavioral-change reconstruction · interpretation is not causal attribution</span>
      </footer>
    </div>
  );
}
