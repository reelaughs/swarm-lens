import type { EpisodeViewModel, TurningPoint } from "../data/types";
import { utcDate } from "../lib/format";

interface Props {
  episode: EpisodeViewModel["episode"];
  points: TurningPoint[];
  selectedRank: number;
  onSelect: (rank: number) => void;
}

function dayLabels(startValue: string, endValue: string): Date[] {
  const start = new Date(startValue);
  const end = new Date(endValue);
  const cursor = new Date(Date.UTC(start.getUTCFullYear(), start.getUTCMonth(), start.getUTCDate()));
  const values: Date[] = [];
  while (cursor <= end) {
    values.push(new Date(cursor));
    cursor.setUTCDate(cursor.getUTCDate() + 1);
  }
  return values;
}

interface MarkerDisplacement {
  x: number;
  y: number;
}

function collisionDisplacements(points: TurningPoint[]): Map<number, MarkerDisplacement> {
  const sorted = [...points].sort((left, right) => left.timelinePositionPercent - right.timelinePositionPercent);
  const groups: TurningPoint[][] = [];
  for (const point of sorted) {
    const group = groups.at(-1);
    const previous = group?.at(-1);
    if (group && previous && point.timelinePositionPercent - previous.timelinePositionPercent < 3.5) {
      group.push(point);
    } else {
      groups.push([point]);
    }
  }
  const displacements = new Map<number, MarkerDisplacement>();
  for (const group of groups) {
    group.forEach((point, index) => {
      if (group.length === 1) {
        displacements.set(point.rank, { x: 0, y: 0 });
        return;
      }
      const direction = index % 2 === 0 ? -1 : 1;
      const tier = Math.floor(index / 2) + 1;
      displacements.set(point.rank, { x: direction * 20 * tier, y: direction * 31 * tier });
    });
  }
  return displacements;
}

export function IncidentTimeline({ episode, points, selectedRank, onSelect }: Props) {
  const days = dayLabels(episode.start, episode.end);
  const displacements = collisionDisplacements(points);
  return (
    <section className="timeline-panel" aria-label="Episode turning-point timeline">
      <div className="timeline-days" aria-hidden="true">
        {days.map((day) => (
          <span key={day.toISOString()}>{utcDate.format(day).replace(/ 2026$/, "")}</span>
        ))}
      </div>
      <div className="timeline-track">
        {points.map((point) => {
          const selected = point.rank === selectedRank;
          const displacement = displacements.get(point.rank) ?? { x: 0, y: 0 };
          const displaced = displacement.x !== 0 || displacement.y !== 0;
          return (
            <span
              className="timeline-anchor"
              key={point.rank}
              style={{ left: `${point.timelinePositionPercent}%` }}
            >
              <span className="timeline-tick" aria-hidden="true" />
              {displaced && (
                <svg className="timeline-leader" width="1" height="1" aria-hidden="true">
                  <line x1="0" y1="0" x2={displacement.x} y2={displacement.y} />
                </svg>
              )}
              <button
                className={`timeline-marker ${selected ? "timeline-marker--selected" : ""}`}
                style={{ left: `${displacement.x}px`, top: `${displacement.y}px` }}
                onClick={() => onSelect(point.rank)}
                aria-pressed={selected}
                aria-describedby={`timeline-tooltip-${point.rank}`}
                aria-label={`Select behavioral-change rank ${point.rank}; timestamp ${point.timestamp}; transition magnitude ${point.aggregateDetectorScore}`}
              >
                <span className="timeline-circle" />
                <span className="timeline-rank">#{point.rank}</span>
                <span className="timeline-tooltip" id={`timeline-tooltip-${point.rank}`} role="tooltip">
                  <time>{point.timestamp}</time>
                  <strong>Transition magnitude {point.aggregateDetectorScore.toFixed(3)}</strong>
                </span>
              </button>
            </span>
          );
        })}
      </div>
    </section>
  );
}
