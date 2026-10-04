"""End-to-end Stage 2 pipeline, kept separate from canonical ingestion."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any, Mapping

import pyarrow.parquet as pq

from .config import TurningPointConfig
from .reporting import plot_scores, render_report, write_csv, write_parquet
from .scoring import COMPONENTS, largest_distribution_changes, rank_peaks, score_window_size
from .topics import fit_or_load_topics
from .windowing import build_windows, eligible_window, inactive_gaps


@dataclass(frozen=True)
class DetectionResult:
    recommended_window_minutes: int | None
    candidate_count: int
    output_dir: Path
    cache_dir: Path


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _public_comparison(row: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if not key.startswith("_")}


def _summary_stats(values: list[int]) -> tuple[int, float, int]:
    return (min(values), float(median(values)), max(values)) if values else (0, 0.0, 0)


def run_detection(
    *,
    canonical_path: Path,
    episode_slug: str,
    config: TurningPointConfig,
    interim_root: Path,
    output_root: Path,
) -> DetectionResult:
    canonical_path = Path(canonical_path)
    rows = pq.read_table(canonical_path).to_pylist()
    if not rows:
        raise ValueError("canonical episode dataset is empty")
    goal_ids = {row["village_goal_id"] for row in rows}
    goals = {row["village_goal_text"] for row in rows}
    starts = {row["village_goal_start"] for row in rows}
    ends = {row["village_goal_end"] for row in rows}
    if len(goal_ids) != 1 or len(goals) != 1 or len(starts) != 1 or len(ends) != 1:
        raise ValueError("canonical rows do not describe exactly one episode")
    episode_end = next(iter(ends))
    if episode_end is None:
        raise ValueError("turning-point detection requires a closed episode interval")
    episode_id = next(iter(goal_ids))
    episode_goal = next(iter(goals))
    episode_start = next(iter(starts))
    input_hash = _hash_file(canonical_path)
    cache_identity = {"input_sha256": input_hash, "config_sha256": config.fingerprint}
    cache_dir = Path(interim_root) / episode_slug / "turning_points" / f"{config.fingerprint[:12]}-{input_hash[:12]}"
    cache_dir.mkdir(parents=True, exist_ok=True)
    communication, intention, cache_hit = fit_or_load_topics(
        rows,
        communication_config=config.communication_model,
        intention_config=config.intention_model,
        random_seed=config.detector.random_seed,
        cache_dir=cache_dir,
        cache_identity=cache_identity,
    )
    agent_rows = [row for row in rows if row["event_kind"] == "high_level_event" and row.get("agent_id")]
    agent_vocabulary = sorted({row["agent_id"] for row in agent_rows})
    action_vocabulary = sorted({row["action_type"] for row in rows if row["event_kind"] == "high_level_event" and row.get("action_type")})
    agent_labels = {
        agent_id: next((row["agent_name"] for row in agent_rows if row["agent_id"] == agent_id and row.get("agent_name")), agent_id)
        for agent_id in agent_vocabulary
    }

    comparisons_by_size: dict[int, list[dict[str, Any]]] = {}
    standardization_by_size: dict[int, dict[str, Any]] = {}
    diagnostics: list[dict[str, Any]] = []
    activity_rows: list[dict[str, Any]] = []
    gap_rows: list[dict[str, Any]] = []
    for minutes in config.detector.window_sizes_minutes:
        windows = build_windows(rows, episode_start, episode_end, minutes)
        gaps = inactive_gaps(windows, minutes)
        comparisons, scoring_meta = score_window_size(
            windows,
            window_minutes=minutes,
            config=config.detector,
            communication=communication,
            intention=intention,
            agent_vocabulary=agent_vocabulary,
            action_vocabulary=action_vocabulary,
        )
        comparisons_by_size[minutes] = comparisons
        standardization_by_size[minutes] = scoring_meta["standardization"]
        active = [window for window in windows if window.active]
        event_counts = [len(window.event_rows) for window in active]
        chat_counts = [len(window.chat_rows) for window in active]
        session_counts = [len(window.session_rows) for window in active]
        event_min, event_median, event_max = _summary_stats(event_counts)
        chat_min, chat_median, chat_max = _summary_stats(chat_counts)
        session_min, session_median, session_max = _summary_stats(session_counts)
        diagnostics.append(
            {
                "window_size_minutes": minutes,
                "total_windows": len(windows),
                "active_windows": len(active),
                "overall_eligible_windows": sum(
                    eligible_window(window, min_events=config.detector.overall_min_high_level_events, min_agents=config.detector.overall_min_distinct_agents)
                    for window in windows
                ),
                "overall_eligible_comparisons": scoring_meta["overall_eligible_comparisons"],
                "valid_aggregate_comparisons": scoring_meta["valid_aggregate_comparisons"],
                "inactive_gap_count": len(gaps),
                "inactive_minutes": sum(gap["duration_minutes"] for gap in gaps),
                "max_inactive_gap_minutes": max((gap["duration_minutes"] for gap in gaps), default=0),
                "event_count_min": event_min,
                "event_count_median": event_median,
                "event_count_max": event_max,
                "chat_count_min": chat_min,
                "chat_count_median": chat_median,
                "chat_count_max": chat_max,
                "session_count_min": session_min,
                "session_count_median": session_median,
                "session_count_max": session_max,
                "reliable": scoring_meta["reliable"],
            }
        )
        for window in active:
            activity_rows.append(
                {
                    "window_size_minutes": minutes,
                    "window_start": window.start,
                    "window_end": window.end,
                    "high_level_event_count": len(window.event_rows),
                    "chat_message_count": len(window.chat_rows),
                    "agent_chat_message_count": len(window.agent_chat_rows),
                    "session_goal_count": len(window.session_rows),
                    "agent_event_count": len(window.agent_event_rows),
                    "distinct_active_agents": window.distinct_agents,
                    "overall_eligible": eligible_window(window, min_events=config.detector.overall_min_high_level_events, min_agents=config.detector.overall_min_distinct_agents),
                }
            )
        for gap in gaps:
            gap_rows.append({"window_size_minutes": minutes, **gap})

    reliable_sizes = [row["window_size_minutes"] for row in diagnostics if row["reliable"]]
    recommended_size = min(reliable_sizes) if reliable_sizes else None
    candidates: list[dict[str, Any]] = []
    min_peak_steps = None
    if recommended_size is not None:
        candidates, min_peak_steps = rank_peaks(
            comparisons_by_size[recommended_size],
            window_minutes=recommended_size,
            min_separation_minutes=config.detector.min_peak_separation_minutes,
            top_k=config.detector.top_k,
        )
        for candidate in candidates:
            distributions = candidate["_distributions"]
            labels = {
                "communication": communication.labels,
                "intention": intention.labels,
                "participation": [agent_labels[agent_id] for agent_id in agent_vocabulary],
                "action_type": action_vocabulary,
            }
            for component in COMPONENTS:
                before, after = distributions[component]
                candidate[f"{component}_changes"] = (
                    largest_distribution_changes(before, after, labels[component], config.detector.top_changes)
                    if before is not None and after is not None and candidate[f"{component}_js"] is not None
                    else []
                )

    public_timeseries = [
        _public_comparison(row)
        for minutes in config.detector.window_sizes_minutes
        for row in comparisons_by_size[minutes]
    ]
    public_candidates = []
    evidence_rows = []
    for candidate in candidates:
        public = _public_comparison(candidate)
        for component in COMPONENTS:
            public[f"{component}_changes_json"] = json.dumps(candidate[f"{component}_changes"], ensure_ascii=False)
            public.pop(f"{component}_changes", None)
        public_candidates.append(public)
        before = candidate["_before_window"]
        after = candidate["_after_window"]
        signal_rows = {
            "communication": lambda window: [row for row in window.agent_chat_rows if row["canonical_event_id"] in communication.weights_by_id],
            "intention": lambda window: [row for row in window.session_rows if row["canonical_event_id"] in intention.weights_by_id],
            "participation": lambda window: window.agent_event_rows,
            "action_type": lambda window: window.event_rows,
        }
        for side, window in (("before", before), ("after", after)):
            for signal, getter in signal_rows.items():
                for row in getter(window):
                    evidence_rows.append(
                        {
                            "candidate_rank": candidate["rank"],
                            "comparison_id": candidate["comparison_id"],
                            "window_side": side,
                            "signal": signal,
                            "canonical_event_id": row["canonical_event_id"],
                            "source_table": row["source_table"],
                            "source_row_id": row["source_row_id"],
                            "event_index": row.get("event_index"),
                            "event_timestamp": row["event_timestamp"],
                        }
                    )

    output_dir = Path(output_root) / episode_slug / "turning_points"
    output_dir.mkdir(parents=True, exist_ok=True)
    write_parquet(output_dir / "transition_timeseries.parquet", public_timeseries)
    write_csv(output_dir / "transition_timeseries.csv", public_timeseries)
    write_parquet(output_dir / "top_candidates.parquet", public_candidates)
    write_parquet(output_dir / "candidate_evidence.parquet", evidence_rows)
    write_csv(output_dir / "windowing_diagnostics.csv", diagnostics)
    write_csv(output_dir / "window_activity.csv", activity_rows)
    write_csv(output_dir / "inactive_gaps.csv", gap_rows)
    write_parquet(cache_dir / "window_activity.parquet", activity_rows)
    write_parquet(cache_dir / "transition_features.parquet", public_timeseries)
    plot_scores(output_dir, {size: [_public_comparison(row) for row in values] for size, values in comparisons_by_size.items()})
    resolved = {
        "configuration": config.as_dict(),
        "configuration_sha256": config.fingerprint,
        "canonical_input_sha256": input_hash,
        "recommended_window_minutes": recommended_size,
        "min_peak_separation_steps_at_recommended_size": min_peak_steps,
    }
    (output_dir / "resolved_configuration.json").write_text(json.dumps(resolved, indent=2, sort_keys=True), encoding="utf-8")
    interval = f"[{episode_start.isoformat()}, {episode_end.isoformat()})"
    report = render_report(
        episode_goal=episode_goal,
        episode_id=episode_id,
        episode_interval=interval,
        config_fingerprint=config.fingerprint,
        cache_hit=cache_hit,
        diagnostic_summaries=diagnostics,
        recommended_size=recommended_size,
        candidates=candidates,
        standardization_by_size=standardization_by_size,
        topic_metadata={"communication": communication.metadata, "intention": intention.metadata},
        min_valid_comparisons=config.detector.min_valid_comparisons,
        min_peak_separation_minutes=config.detector.min_peak_separation_minutes,
    )
    (output_dir / "report.md").write_text(report, encoding="utf-8", newline="\n")
    return DetectionResult(recommended_size, len(candidates), output_dir, cache_dir)
