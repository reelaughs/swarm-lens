import { useState } from "react";
import type { DistributionChange, Signal } from "../data/types";
import { InfoPopover } from "./InfoPopover";

interface DirectionalChanges {
  increase: DistributionChange | null;
  decrease: DistributionChange | null;
}

export function percentagePointDelta(value: number): string {
  const amount = Math.abs(value * 100).toFixed(1);
  return `${value >= 0 ? "+" : "−"}${amount} pp`;
}

const FAMILY_COPY = {
  communication: {
    subtitle: "Latent communication topics",
    help: "Communication topics are patterns discovered from chat messages by the frozen NMF topic model. Labels such as C01 are topic-component IDs. The words shown are the highest-weight terms characterizing that topic. A rise means that topic became more prevalent after the turning-point boundary; it does not mean each listed word individually increased.",
  },
  intention: {
    subtitle: "Latent session-goal topics",
    help: "Intention topics are patterns discovered separately from agents' session_goal text. Labels such as I01 are topic-component IDs. The displayed terms characterize the latent topic. A rise means that intention pattern became more prevalent after the boundary.",
  },
  participation: {
    subtitle: "Share of observed agent activity",
    help: "Participation measures how observed activity is distributed across agents. A rise for an agent means that agent accounts for a larger share of activity after the boundary; a fall means a smaller share. This measures relative participation, not effectiveness or importance.",
  },
  action_type: {
    subtitle: "Share of high-level event types",
    help: "Action type measures how high-level event categories are distributed before and after the boundary. Labels such as CONSOLIDATE and PAUSE are literal event categories from the frozen event representation. A rise means that event type became more common after the boundary.",
  },
} as const;

export const HOW_TO_READ_SIGNALS = "These cards compare distributions before and after the detected boundary. Communication and Intention use learned latent topics; Participation uses agents; Action type uses event categories. Direction indicates relative change, not whether the change is good or bad.";

const TOP_TERMS_HELP = "These are the highest-weight words and phrases in this learned topic. They show what language most strongly defines the topic. They are descriptors of the topic, not separate events or quantities that individually increased. The topic model uses both single words and two-word phrases, so related terms may both appear.";

export function largestDirectionalChanges(changes: DistributionChange[]): DirectionalChanges {
  let increase: DistributionChange | null = null;
  let decrease: DistributionChange | null = null;

  for (const change of changes) {
    if (change.delta > 0 && (!increase || change.delta > increase.delta)) increase = change;
    if (change.delta < 0 && (!decrease || change.delta < decrease.delta)) decrease = change;
  }

  return { increase, decrease };
}

function parseTopicLabel(label: string): { id: string; keywords: string[] } | null {
  const match = label.match(/^([CI]\d+):\s*(.+)$/);
  if (!match) return null;
  return {
    id: match[1],
    keywords: match[2].split(",").map((value) => value.trim()).filter(Boolean),
  };
}

function TopicKeywords({ keywords, compact }: { keywords: string[]; compact: boolean }) {
  const [expanded, setExpanded] = useState(false);
  const visibleCount = compact ? 4 : 5;
  const hiddenCount = Math.max(0, keywords.length - visibleCount);
  const visible = expanded ? keywords : keywords.slice(0, visibleCount);

  return (
    <div className="shift-keywords">
      <div className="shift-keywords-heading">
        <span>Top terms defining this topic</span>
        <InfoPopover label="About the terms defining this topic">{TOP_TERMS_HELP}</InfoPopover>
      </div>
      <span>{visible.join(" · ")}</span>
      {hiddenCount > 0 && (
        <button
          type="button"
          className="keyword-toggle"
          onClick={() => setExpanded((value) => !value)}
          aria-expanded={expanded}
        >
          {expanded ? "Show less" : `+${hiddenCount} more`}
        </button>
      )}
    </div>
  );
}

function ShiftRow({
  change,
  direction,
  compact,
  signalId,
}: {
  change: DistributionChange | null;
  direction: "increase" | "decrease";
  compact: boolean;
  signalId: Signal["id"];
}) {
  const topic = change ? parseTopicLabel(change.label) : null;
  const topicSignal = signalId === "communication" || signalId === "intention";
  const directionLabel = topicSignal
    ? direction === "increase" ? "More prevalent after boundary" : "Less prevalent after boundary"
    : signalId === "participation"
      ? direction === "increase" ? "More active after boundary" : "Less active after boundary"
      : direction === "increase" ? "More common after boundary" : "Less common after boundary";
  return (
    <div className={`shift-row shift-row--${direction}`}>
      <div className="shift-direction">
        <span aria-hidden="true">{direction === "increase" ? "↑" : "↓"}</span>
        <span>{directionLabel}</span>
        <strong
          aria-label={change ? `${percentagePointDelta(change.delta)}; exact normalized share difference ${change.delta}` : undefined}
          title={change ? `Exact normalized share difference: ${change.delta}` : undefined}
        >
          {change ? percentagePointDelta(change.delta) : "Not available"}
        </strong>
      </div>
      {change && (
        <div className="shift-subject">
          {topic ? (
            <>
              <span className="topic-kind">
                {signalId === "communication" ? "Machine-learned chat topic" : "Machine-learned session-goal topic"}
              </span>
              <code>Topic {topic.id}</code>
              <TopicKeywords keywords={topic.keywords} compact={compact} />
            </>
          ) : (
            <>
              <span className="shift-subject-kind">{signalId === "participation" ? "Agent" : "Action category"}</span>
              <strong>{change.label}</strong>
            </>
          )}
        </div>
      )}
    </div>
  );
}

export function DetectorShifts({ signals, compact = false }: { signals: Signal[]; compact?: boolean }) {
  return (
    <div className={`detector-shifts ${compact ? "detector-shifts--compact" : ""}`}>
      {signals.map((signal) => {
        const changes = largestDirectionalChanges(signal.distributionChanges);
        const family = FAMILY_COPY[signal.id];
        return (
          <section className={`detector-shift detector-shift--${signal.id}`} key={signal.id}>
            <header>
              <span className="signal-dot" aria-hidden="true" />
              <div className="detector-shift-title">
                <div>
                  <h3>{signal.label}</h3>
                  <InfoPopover label={`About ${signal.label}`}>{family.help}</InfoPopover>
                </div>
                <p>{family.subtitle}</p>
              </div>
            </header>
            <div className="shift-pair">
              <ShiftRow change={changes.increase} direction="increase" compact={compact} signalId={signal.id} />
              <ShiftRow change={changes.decrease} direction="decrease" compact={compact} signalId={signal.id} />
            </div>
          </section>
        );
      })}
    </div>
  );
}
