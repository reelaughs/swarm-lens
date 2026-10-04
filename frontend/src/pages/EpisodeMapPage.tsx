import { useState } from "react";
import { IncidentTimeline } from "../components/IncidentTimeline";
import { DetectorShifts, HOW_TO_READ_SIGNALS } from "../components/DetectorShifts";
import { InfoPopover } from "../components/InfoPopover";
import { SignalCards } from "../components/SignalCards";
import type { EpisodeViewModel } from "../data/types";
import { titleCase, utcDate, utcDateTime } from "../lib/format";

interface Props {
  data: EpisodeViewModel;
  onInvestigate: (rank: number) => void;
}

export function EpisodeMapPage({ data, onInvestigate }: Props) {
  const [selectedRank, setSelectedRank] = useState(1);
  const point = data.turningPoints.find((value) => value.rank === selectedRank)!;
  const primary = point.interpretation.socialProcessEvaluation.hypotheses.find(
    (value) => value.interpretation_role === "best_supported_candidate",
  );

  return (
    <main className="page-shell episode-page">
      <section className="episode-hero">
        <div>
          <div className="eyebrow">Episode / Incident map</div>
          <h1>{data.episode.goalText}</h1>
          <p>
            {utcDate.format(new Date(data.episode.start))} — {utcDate.format(new Date(data.episode.end))}
            {" · "}{data.episode.recordCount.toLocaleString()} canonical records
            {" · "}{data.episode.turningPointCount} detected behavioral turning points
          </p>
        </div>
        <div className="ranking-key">
          <span>Ranked by behavioral change</span>
          <span><i /> selected turning point</span>
          <span>Hover or focus for timestamp and magnitude.</span>
          <span>Rank is not importance.</span>
        </div>
      </section>

      <IncidentTimeline
        episode={data.episode}
        points={data.turningPoints}
        selectedRank={selectedRank}
        onSelect={setSelectedRank}
      />

      <section className="legend-block">
        <div className="section-label">Detector signal families</div>
        <SignalCards signals={point.signals} compact />
      </section>

      <section className="selected-preview">
        <div className="preview-main">
          <div className="preview-kicker">
            <span>Selected turning point #{point.rank}</span>
            <time>{utcDateTime.format(new Date(point.timestamp))} UTC</time>
          </div>
          <h2>Turning point #{point.rank}</h2>
          <div className="preview-columns">
            <div>
              <div className="section-title-with-help">
                <div className="section-label">What changed?</div>
                <InfoPopover label="How to read these signals">{HOW_TO_READ_SIGNALS}</InfoPopover>
              </div>
              <p className="shift-explainer">Largest before/after distribution-share changes; arrows indicate direction only.</p>
              <DetectorShifts signals={point.signals} compact />
            </div>
            <div>
              <div className="section-label">Analyst interpretation</div>
              <p className="analyst-copy">{point.interpretation.analystNote.summary}</p>
              <p className="method-note">Interpretation of the evidence neighborhood, not a causal explanation.</p>
            </div>
          </div>
        </div>
        <aside className="preview-aside">
          <div className="section-label">Possible social process</div>
          <h3>{primary?.display_name ?? "No clear social-process match"}</h3>
          {primary && (
            <div className="interpretation-metrics">
              <div><span>Confidence</span><strong>{titleCase(primary.displayed_confidence)}</strong></div>
              <div><span>Evidence diversity</span><strong>{titleCase(primary.evidence_diversity)}</strong></div>
            </div>
          )}
          <p className="method-note">Possible process does not mean cause.</p>
          <button className="outline-button" onClick={() => onInvestigate(point.rank)}>
            Investigate turning point →
          </button>
        </aside>
      </section>
    </main>
  );
}
