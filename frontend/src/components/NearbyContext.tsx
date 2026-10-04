import type { CompactEvidence, ExternalContextEvent, TurningPoint } from "../data/types";
import { investigatorText } from "../lib/presentationLanguage";

export interface NearbyContextItem {
  key: string;
  timestamp: string;
  eventType: string;
  actor: string | null;
  text: string | null;
  relativeTiming: string;
  provenance: string | null;
}

function eventTypeForEvidence(item: CompactEvidence): string {
  const reasons = item.selectionReasons.join(" ").toLowerCase();
  if (reasons.includes("human_intervention")) return "Human / administrator message";
  if (reasons.includes("automated_nudge")) return "Automated nudge";
  if (reasons.includes("session boundary")) return "Session boundary";
  if (reasons.includes("agent join")) return "Agent joined";
  if (reasons.includes("agent departure")) return "Agent departure";
  if (reasons.includes("goal boundary")) return "Village-goal boundary";
  if (reasons.includes("scaffold")) return "Scaffolding change";
  return item.actionType === "USER_TALK" ? "Context message" : "Context event";
}

function eventTypeForStructured(item: ExternalContextEvent): string {
  const labels: Record<string, string> = {
    user_talk: "Human / administrator message",
    administrator_message: "Human / administrator message",
    automated_nudge: "Automated nudge",
    agent_join: "Agent joined",
    agent_departure: "Agent departure",
    village_goal_boundary: "Village-goal boundary",
    scaffolding_change: "Scaffolding change",
    session_boundary: "Session boundary",
  };
  return labels[item.type.toLowerCase()] ?? "Context event";
}

export function relativeContextTiming(
  timestamp: string,
  boundary: string,
  precision = "timestamp",
): string {
  if (precision !== "timestamp") {
    const contextDay = timestamp.slice(0, 10);
    const boundaryDay = boundary.slice(0, 10);
    return contextDay === boundaryDay ? "Same day" : `Dated ${contextDay}`;
  }
  const differenceMinutes = (Date.parse(timestamp) - Date.parse(boundary)) / 60_000;
  const magnitude = Math.abs(differenceMinutes);
  if (magnitude < 1) {
    if (differenceMinutes === 0) return "At boundary";
    return `<1 min ${differenceMinutes < 0 ? "before" : "after"}`;
  }
  return `${Math.round(magnitude)} min ${differenceMinutes < 0 ? "before" : "after"}`;
}

export function nearbyContextItems(point: TurningPoint): NearbyContextItem[] {
  const evidenceItems = point.compactEvidence
    .filter((item) => item.categories.includes("external_context"))
    .map((item) => ({
      key: `evidence:${item.id}`,
      timestamp: item.timestamp,
      eventType: eventTypeForEvidence(item),
      actor: item.agentName ?? item.agentModel,
      text: item.text,
      relativeTiming: relativeContextTiming(item.timestamp, point.timestamp),
      provenance: item.id,
    }));
  const structuredItems = point.externalContextEvents.map((item, index) => ({
    key: `structured:${item.type}:${item.time_or_date}:${index}`,
    timestamp: item.time_or_date,
    eventType: eventTypeForStructured(item),
    actor: null,
    text: investigatorText(item.description),
    relativeTiming: relativeContextTiming(item.time_or_date, point.timestamp, item.precision),
    provenance: item.provenance,
  }));
  return [...evidenceItems, ...structuredItems].sort((left, right) =>
    left.timestamp.localeCompare(right.timestamp),
  );
}

export function NearbyContext({ point }: { point: TurningPoint }) {
  const items = nearbyContextItems(point);
  if (items.length === 0) return null;

  return (
    <section className="detail-section nearby-context-section">
      <div className="section-heading-row">
        <div className="section-label">Nearby context</div>
        <span>Contextual coincidence · not causal attribution</span>
      </div>
      <div className="nearby-context-list">
        {items.map((item) => (
          <article className="nearby-context-item" key={item.key}>
            <div className="nearby-context-meta">
              <strong>{item.eventType}</strong>
              <time dateTime={item.timestamp}>{item.relativeTiming}</time>
            </div>
            {item.actor ? <span className="nearby-context-actor">{item.actor}</span> : null}
            {item.text ? <p>{item.text}</p> : <p>No textual content recorded.</p>}
            {item.provenance ? <code>{item.provenance}</code> : null}
          </article>
        ))}
      </div>
      <p className="context-caveat">
        These events are shown because they occur near the detected boundary. Temporal proximity does not establish influence or causation.
      </p>
    </section>
  );
}
