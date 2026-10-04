import { useEffect, useState } from "react";
import { SiteHeader } from "./components/SiteHeader";
import { loadEpisode } from "./data/loadEpisode";
import type { EpisodeViewModel } from "./data/types";
import { EpisodeMapPage } from "./pages/EpisodeMapPage";
import { TurningPointPage } from "./pages/TurningPointPage";

function rankFromPath(): number | null {
  const match = window.location.pathname.match(/\/turning-points\/(\d+)\/?$/);
  return match ? Number(match[1]) : null;
}

export default function App() {
  const [data, setData] = useState<EpisodeViewModel | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [rank, setRank] = useState<number | null>(() => rankFromPath());

  useEffect(() => {
    loadEpisode().then(setData).catch((reason: unknown) => {
      setError(reason instanceof Error ? reason.message : "Could not load frozen episode data.");
    });
  }, []);

  useEffect(() => {
    const onPopState = () => setRank(rankFromPath());
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const navigate = (nextRank: number | null) => {
    const path = nextRank === null
      ? "/episodes/perform-novel-research"
      : `/episodes/perform-novel-research/turning-points/${nextRank}`;
    window.history.pushState({}, "", path);
    setRank(nextRank);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  if (error) return <main className="state-message"><h1>SwarmLens</h1><p>{error}</p></main>;
  if (!data) return <main className="state-message"><p>Loading frozen episode…</p></main>;
  const point = rank === null ? null : data.turningPoints.find((value) => value.rank === rank);

  return (
    <div className="app-shell">
      <SiteHeader label={data.presentation.label} />
      {point ? (
        <TurningPointPage data={data} point={point} onBack={() => navigate(null)} />
      ) : (
        <EpisodeMapPage data={data} onInvestigate={(value) => navigate(value)} />
      )}
      <footer className="site-footer">
        <span>SwarmLens</span>
        <span>Frozen behavioral-change reconstruction · interpretation is not causal attribution</span>
      </footer>
    </div>
  );
}
