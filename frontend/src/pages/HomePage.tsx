import type { MouseEvent } from "react";
import type { EpisodeCatalogEntry } from "../data/types";
import { utcDate } from "../lib/format";
import { episodePath } from "../lib/routes";

interface Props {
  episodes: EpisodeCatalogEntry[];
  onOpenEpisode: (slug: string) => void;
}

export function HomePage({ episodes, onOpenEpisode }: Props) {
  const openEpisode = (event: MouseEvent<HTMLAnchorElement>, slug: string) => {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    onOpenEpisode(slug);
  };

  return (
    <main className="page-shell home-page">
      <section className="home-hero">
        <div className="eyebrow">SwarmLens</div>
        <h1>Investigate collective behavior</h1>
        <p>
          SwarmLens surfaces population-level behavioral turning points, reconstructs source-linked
          evidence around them, and proposes bounded interpretations for investigation.
        </p>
      </section>

      <div className="launcher-grid">
        <section className="launcher-panel launcher-panel--upcoming" aria-labelledby="analyze-heading">
          <div className="launcher-number">01</div>
          <div className="section-label">Analyze a dataset</div>
          <h2 id="analyze-heading">Analyze dataset</h2>
          <p>
            Upload a multi-agent interaction dataset, validate it, choose an episode or time window,
            and run a retrospective swarm investigation.
          </p>
          <div className="upcoming-workflow" aria-label="Dataset ingestion coming next">
            <span>Upcoming workflow</span>
            <strong>Dataset ingestion coming next</strong>
            <small>
              Initial support will use the AI Village schema, with an adapter-based path for additional
              multi-agent datasets.
            </small>
          </div>
        </section>

        <section className="launcher-panel" aria-labelledby="examples-heading">
          <div className="launcher-number">02</div>
          <div className="section-label">Explore an example</div>
          <h2 id="examples-heading">Precomputed investigations</h2>
          <div className="example-list">
            {episodes.map((episode) => (
              <a
                className="example-card"
                href={episodePath(episode.slug)}
                key={episode.slug}
                onClick={(event) => openEpisode(event, episode.slug)}
              >
                <div className="example-card-topline">
                  {episode.status && <span className="example-status">{episode.status.label}</span>}
                  <span aria-hidden="true">Explore →</span>
                </div>
                <h3>{episode.title}</h3>
                <time>
                  {utcDate.format(new Date(episode.start))} — {utcDate.format(new Date(episode.end))}
                </time>
                <p>{episode.turningPointCount} detected behavioral turning points</p>
              </a>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}
