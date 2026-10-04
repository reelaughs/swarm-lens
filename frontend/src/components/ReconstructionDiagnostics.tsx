import type { TurningPoint } from "../data/types";
import {
  investigatorStructure,
  investigatorText,
} from "../lib/presentationLanguage";

export function ReconstructionDiagnostics({ point }: { point: TurningPoint }) {
  return (
    <details className="diagnostics disclosure">
      <summary>
        <span>Reconstruction diagnostics</span>
        <span aria-hidden="true" className="disclosure-icon">+</span>
      </summary>
      <div className="diagnostics-body">
        <h3>Ranked preceding evidence</h3>
        <ol className="preceding-list">
          {point.reconstruction.rankedPrecedingEvidence.map((item) => (
            <li key={item.logicalItemId}>
              <div className="preceding-meta">
                <span>#{item.rank}</span>
                <span>{item.agentName ?? "Unattributed"}</span>
                <span>Support: {item.antecedentSupport ?? "unknown"}</span>
              </div>
              <p>{item.text ?? "No textual content recorded."}</p>
              <code>{item.logicalItemId}</code>
            </li>
          ))}
        </ol>
        <div className="diagnostic-grid">
          <div>
            <h3>Null findings</h3>
            {point.reconstruction.nullFindings.length ? (
              <ul>{point.reconstruction.nullFindings.map((value) => <li key={value}>{investigatorText(value)}</li>)}</ul>
            ) : <p>None recorded.</p>}
          </div>
          <div>
            <h3>Caveats</h3>
            <ul>{point.reconstruction.caveats.map((value) => <li key={value}>{investigatorText(value)}</li>)}</ul>
          </div>
        </div>
        <details className="raw-structure">
          <summary>Structural observations</summary>
          <p className="method-note">Same-window co-activity is activity-density context, not relational evidence.</p>
          <pre>{JSON.stringify(investigatorStructure(point.reconstruction.structuralObservations), null, 2)}</pre>
        </details>
      </div>
    </details>
  );
}
