import type { ReferencedEvidence } from "../data/types";

export function ProvenanceDisclosure({ evidence }: { evidence: ReferencedEvidence[] }) {
  return (
    <details className="disclosure">
      <summary>
        <span>05 · Provenance / raw trace</span>
        <span aria-hidden="true" className="disclosure-icon">+</span>
      </summary>
      <div className="provenance-list">
        {evidence.map((item) => (
          <details className="provenance-item" key={item.evidenceId}>
            <summary>
              <code>{item.evidenceId}</code>
              <span>{String(item.record.evidence_kind ?? "evidence")}</span>
            </summary>
            <div className="provenance-body">
              {item.record.text ? <p>{String(item.record.text)}</p> : null}
              {item.record.description ? <p>{String(item.record.description)}</p> : null}
              <pre>{JSON.stringify(item.provenance, null, 2)}</pre>
            </div>
          </details>
        ))}
      </div>
    </details>
  );
}
