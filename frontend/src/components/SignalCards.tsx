import type { Signal } from "../data/types";
import { signed } from "../lib/format";

export function SignalCards({ signals, compact = false }: { signals: Signal[]; compact?: boolean }) {
  return (
    <div className={`signal-cards ${compact ? "signal-cards--compact" : ""}`}>
      {signals.map((signal) => (
        <div className={`signal-card signal-card--${signal.id}`} key={signal.id}>
          <div className="signal-label">
            <span className="signal-dot" />
            {signal.label}
          </div>
          {!compact && (
            <>
              <strong className="signal-value">
                {signal.eligible ? signed(signal.standardizedScore) : "Underpowered"}
              </strong>
              <span className="signal-raw">
                Raw JS {signal.jensenShannonDivergence?.toFixed(3) ?? "unavailable"}
              </span>
            </>
          )}
        </div>
      ))}
    </div>
  );
}
