import { EvidenceSequence } from "../components/EvidenceSequence";
import { DetectorShifts, HOW_TO_READ_SIGNALS } from "../components/DetectorShifts";
import { InfoPopover } from "../components/InfoPopover";
import { NearbyContext } from "../components/NearbyContext";
import { ProvenanceDisclosure } from "../components/ProvenanceDisclosure";
import { ReconstructionDiagnostics } from "../components/ReconstructionDiagnostics";
import { SignalCards } from "../components/SignalCards";
import { SocialProcessPanel } from "../components/SocialProcessPanel";
import type { EpisodeViewModel, TurningPoint } from "../data/types";
import { utcDateTime } from "../lib/format";
import { investigatorText } from "../lib/presentationLanguage";

interface Props {
  data: EpisodeViewModel;
  point: TurningPoint;
  onBack: () => void;
}

export function TurningPointPage({ data, point, onBack }: Props) {
  return (
    <main className="page-shell detail-page">
      <button className="back-button" onClick={onBack}>← Incident map</button>
      <header className="detail-hero">
        <div>
          <div className="eyebrow">
            Turning point #{point.rank} · {utcDateTime.format(new Date(point.timestamp))} UTC
          </div>
          <h1>Turning point #{point.rank}</h1>
        </div>
        <div className="detail-identity">
          <strong>Behavioral-change rank #{point.rank}</strong>
          <span>Source-linked reconstruction</span>
          <span>Transition magnitude {point.aggregateDetectorScore.toFixed(3)}</span>
        </div>
      </header>

      <div className="investigation-grid">
        <div className="investigation-main">
          <section className="detail-section what-changed">
            <div className="section-title-with-help">
              <div className="section-label">01 · What changed?</div>
              <InfoPopover label="How to read these signals">{HOW_TO_READ_SIGNALS}</InfoPopover>
            </div>
            <div className="detector-score-heading">
              <div>
                <h2>Standardized detector scores</h2>
                <p>Comparable signal-level change scores at this boundary; these are distinct from the distribution deltas below.</p>
              </div>
            </div>
            <SignalCards signals={point.signals} />
            <div className="distribution-heading">
              <h2>Largest underlying distribution shifts</h2>
              <p>Within-family before/after share changes. Arrows indicate direction only, not favorable or unfavorable movement.</p>
            </div>
            <DetectorShifts signals={point.signals} />
            <div className="activity-strip">
              <div>
                <span>Before window</span>
                <strong>{point.activity.before.eventCount} events</strong>
                <small>{point.activity.before.distinctAgents} agents</small>
              </div>
              <div>
                <span>After window</span>
                <strong>{point.activity.after.eventCount} events</strong>
                <small>{point.activity.after.distinctAgents} agents</small>
              </div>
              <div>
                <span>Context flags</span>
                <strong>{point.contextFlags.length}</strong>
                <small>{point.contextFlags.join(" · ") || "None recorded"}</small>
              </div>
            </div>
          </section>

          <NearbyContext point={point} />

          <section className="detail-section evidence-section">
            <div className="section-heading-row">
              <div className="section-label">02 · Evidence sequence</div>
              <span>Evidence brief · detector boundary</span>
            </div>
            <EvidenceSequence evidence={point.compactEvidence} boundary={point.timestamp} />
          </section>

          <ReconstructionDiagnostics point={point} />
        </div>

        <aside className="investigation-aside">
          <section className="analyst-panel">
            <div className="section-label">03 · Analyst interpretation</div>
            <p className="analyst-lede">{investigatorText(point.interpretation.analystNote.summary)}</p>
            <p className="causal-warning">
              This describes the evidence neighborhood around the detected transition. It does not establish what caused the population-level change.
            </p>
          </section>
          <SocialProcessPanel evaluation={point.interpretation.socialProcessEvaluation} />
          <ProvenanceDisclosure evidence={point.referencedEvidence} />
          <details className="disclosure source-disclosure">
            <summary>
              <span>Source provenance</span>
              <span aria-hidden="true" className="disclosure-icon">+</span>
            </summary>
            <div className="source-list">
              <div><strong>Behavioral-change detection</strong><span>Frozen detector candidate</span></div>
              <div><strong>Evidence brief</strong><span>Compact source-linked context</span></div>
              <div><strong>Evidence reconstruction</strong><span>Ranked preceding evidence and diagnostics</span></div>
              <div><strong>Analyst interpretation</strong><span>Bounded interpretation with cited evidence</span></div>
              <div><strong>Episode ID</strong><code>{data.episode.goalId}</code></div>
            </div>
          </details>
        </aside>
      </div>
    </main>
  );
}
