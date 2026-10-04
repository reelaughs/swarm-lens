import { useMemo, useState } from "react";
import type { CompactEvidence } from "../data/types";
import { titleCase, utcTime } from "../lib/format";

type SequenceItem =
  | { type: "evidence"; value: CompactEvidence }
  | { type: "boundary"; timestamp: string };

export function EvidenceSequence({ evidence, boundary }: { evidence: CompactEvidence[]; boundary: string }) {
  const [expanded, setExpanded] = useState(false);
  const sequence = useMemo<SequenceItem[]>(() => {
    const values: SequenceItem[] = evidence.map((value) => ({ type: "evidence", value }));
    values.push({ type: "boundary", timestamp: boundary });
    return values.sort((left, right) => {
      const leftTime = left.type === "boundary" ? left.timestamp : left.value.timestamp;
      const rightTime = right.type === "boundary" ? right.timestamp : right.value.timestamp;
      return leftTime.localeCompare(rightTime);
    });
  }, [evidence, boundary]);
  const visible = expanded ? sequence : sequence.slice(0, 9);

  return (
    <>
      <div className="evidence-sequence">
        {visible.map((item) => {
          if (item.type === "boundary") {
            return (
              <div className="evidence-row evidence-row--boundary" key={`boundary-${item.timestamp}`}>
                <time>{utcTime.format(new Date(item.timestamp))}</time>
                <strong>Detector boundary</strong>
                <span>Population</span>
                <p>Adjacent eligible windows meet at this detected transition boundary.</p>
              </div>
            );
          }
          const value = item.value;
          return (
            <div className="evidence-row" key={value.id}>
              <time>{utcTime.format(new Date(value.timestamp))}</time>
              <strong>{titleCase(value.eventKind ?? value.actionType ?? "record")}</strong>
              <span>{value.agentName ?? value.agentModel ?? "Unattributed"}</span>
              <p>{value.text ?? "No textual content recorded."}</p>
            </div>
          );
        })}
      </div>
      {sequence.length > 9 && (
        <button className="text-button" onClick={() => setExpanded((value) => !value)}>
          {expanded ? "Show compact sequence" : `Show all ${sequence.length} items`}
        </button>
      )}
    </>
  );
}
