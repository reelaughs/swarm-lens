import type { MouseEvent } from "react";
import type { EpisodeCatalogEntry } from "../data/types";
import { utcDate } from "../lib/format";
import { episodePath } from "../lib/routes";
import { DatasetLauncher } from "../components/DatasetLauncher";
import { browserRouteHref } from "../lib/hosting";

interface Props {
  episodes: EpisodeCatalogEntry[];
  hostedDemo?: boolean;
  onOpenEpisode: (slug: string) => void;
  onDatasetCreated: (datasetId: string) => void;
}

export function HomePage({ episodes, hostedDemo = false, onOpenEpisode, onDatasetCreated }: Props) {
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

      {hostedDemo && (
        <aside className="hosted-demo-note" aria-label="Hosted demo status">
          <strong>Hosted read-only demo</strong>
          <span>
            Explore precomputed SwarmLens investigations here. Dataset upload and runtime analysis
            are available when running SwarmLens locally.
          </span>
        </aside>
      )}

      <div className="launcher-grid">
        <section className="launcher-panel" aria-labelledby="analyze-heading">
          <div className="launcher-number">01</div>
          <div className="section-label">Analyze a dataset</div>
          <h2 id="analyze-heading">Analyze dataset</h2>
          <p>
            Upload a multi-agent interaction dataset, validate it, choose an episode,
            and run a retrospective swarm investigation.
          </p>
          <DatasetLauncher hostedDemo={hostedDemo} onCreated={onDatasetCreated} />
          <p className="workflow-note">Custom investigation windows and additional dataset adapters are planned.</p>
        </section>

        <section className="launcher-panel" aria-labelledby="examples-heading">
          <div className="launcher-number">02</div>
          <div className="section-label">Explore an example</div>
          <h2 id="examples-heading">Precomputed investigations</h2>
          <div className="example-list">
            {episodes.map((episode) => (
              <a
                className="example-card"
                href={browserRouteHref(episodePath(episode.slug))}
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
