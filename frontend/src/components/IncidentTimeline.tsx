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

function leaderGeometry(displacement: MarkerDisplacement) {
  const padding = 1;
  const left = Math.min(0, displacement.x) - padding;
  const top = Math.min(0, displacement.y) - padding;
  const width = Math.abs(displacement.x) + padding * 2;
  const height = Math.abs(displacement.y) + padding * 2;
  return {
    left,
    top,
    width,
    height,
    x1: -left,
    y1: -top,
    x2: displacement.x - left,
    y2: displacement.y - top,
  };
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
          const leader = displaced ? leaderGeometry(displacement) : null;
          return (
            <span
              className="timeline-anchor"
              key={point.rank}
              style={{ left: `${point.timelinePositionPercent}%` }}
            >
              <span className="timeline-tick" aria-hidden="true" />
              {leader && (
                <svg
                  className="timeline-leader"
                  width={leader.width}
                  height={leader.height}
                  viewBox={`0 0 ${leader.width} ${leader.height}`}
                  style={{ left: `${leader.left}px`, top: `${leader.top}px` }}
                  aria-hidden="true"
                >
                  <line x1={leader.x1} y1={leader.y1} x2={leader.x2} y2={leader.y2} />
                </svg>
              )}
              <button
                className={`timeline-marker ${displacement.x < 0 ? "timeline-marker--label-left" : ""} ${selected ? "timeline-marker--selected" : ""}`}
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
