"""Component-specific eligibility, divergences, aggregation, and peak ranking."""

from __future__ import annotations

import math
from collections import Counter
from datetime import timedelta
from typing import Any, Mapping, Sequence

import numpy as np

from .config import DetectorConfig
from .distributions import aggregate_available, count_distribution, js_divergence, normalize_distribution, robust_standardize
from .topics import TopicRepresentation
from .windowing import Window, eligible_adjacent_pairs

COMPONENTS = ("communication", "intention", "participation", "action_type")


def _topic_distribution(window_rows: Sequence[Mapping[str, Any]], representation: TopicRepresentation) -> tuple[np.ndarray | None, int]:
    vectors = [representation.weights_by_id[row["canonical_event_id"]] for row in window_rows if row["canonical_event_id"] in representation.weights_by_id]
    if not vectors:
        return None, 0
    return normalize_distribution(np.sum(vectors, axis=0)), len(vectors)


def score_window_size(
    windows: list[Window],
    *,
    window_minutes: int,
    config: DetectorConfig,
    communication: TopicRepresentation,
    intention: TopicRepresentation,
    agent_vocabulary: Sequence[str],
    action_vocabulary: Sequence[str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    pairs = eligible_adjacent_pairs(
        windows,
        min_events=config.overall_min_high_level_events,
        min_agents=config.overall_min_distinct_agents,
    )
    comparisons: list[dict[str, Any]] = []
    for before, after in pairs:
        before_comm, before_comm_n = _topic_distribution(before.agent_chat_rows, communication)
        after_comm, after_comm_n = _topic_distribution(after.agent_chat_rows, communication)
        before_int, before_int_n = _topic_distribution(before.session_rows, intention)
        after_int, after_int_n = _topic_distribution(after.session_rows, intention)
        before_part = count_distribution(Counter(row["agent_id"] for row in before.agent_event_rows), agent_vocabulary)
        after_part = count_distribution(Counter(row["agent_id"] for row in after.agent_event_rows), agent_vocabulary)
        before_action = count_distribution(Counter(row["action_type"] for row in before.event_rows), action_vocabulary)
        after_action = count_distribution(Counter(row["action_type"] for row in after.event_rows), action_vocabulary)

        eligible = {
            "communication": before_comm_n >= config.communication_min_documents_per_window and after_comm_n >= config.communication_min_documents_per_window,
            "intention": before_int_n >= config.intention_min_documents_per_window and after_int_n >= config.intention_min_documents_per_window,
            "participation": (
                len(before.agent_event_rows) >= config.participation_min_agent_events_per_window
                and len(after.agent_event_rows) >= config.participation_min_agent_events_per_window
                and before.distinct_agents >= config.participation_min_distinct_agents
                and after.distinct_agents >= config.participation_min_distinct_agents
            ),
            "action_type": len(before.event_rows) >= config.action_type_min_events_per_window and len(after.event_rows) >= config.action_type_min_events_per_window,
        }
        distributions = {
            "communication": (before_comm, after_comm),
            "intention": (before_int, after_int),
            "participation": (before_part, after_part),
            "action_type": (before_action, after_action),
        }
        raw = {
            component: js_divergence(*distributions[component]) if eligible[component] and all(value is not None for value in distributions[component]) else None
            for component in COMPONENTS
        }
        comparisons.append(
            {
                "comparison_id": f"{window_minutes}m:{after.start.isoformat()}",
                "window_size_minutes": window_minutes,
                "before_window_start": before.start,
                "before_window_end": before.end,
                "after_window_start": after.start,
                "after_window_end": after.end,
                "transition_timestamp": after.start,
                "before_event_count": len(before.event_rows),
                "after_event_count": len(after.event_rows),
                "before_agent_chat_count": before_comm_n,
                "after_agent_chat_count": after_comm_n,
                "before_session_count": before_int_n,
                "after_session_count": after_int_n,
                "before_agent_event_count": len(before.agent_event_rows),
                "after_agent_event_count": len(after.agent_event_rows),
                "before_distinct_agents": before.distinct_agents,
                "after_distinct_agents": after.distinct_agents,
                **{f"{component}_eligible": eligible[component] for component in COMPONENTS},
                **{f"{component}_js": raw[component] for component in COMPONENTS},
                "_before_window": before,
                "_after_window": after,
                "_distributions": distributions,
            }
        )

    standardization: dict[str, Any] = {}
    for component in COMPONENTS:
        standardized, metadata = robust_standardize(
            [row[f"{component}_js"] for row in comparisons],
            min_valid=config.min_valid_comparisons,
        )
        standardization[component] = metadata
        for row, value in zip(comparisons, standardized):
            row[f"{component}_z"] = value

    for row in comparisons:
        aggregate, contributors = aggregate_available(
            {component: row[f"{component}_z"] for component in COMPONENTS},
            minimum_components=config.min_components_for_aggregate,
        )
        row["aggregate_score"] = aggregate
        row["contributing_components"] = ",".join(contributors)
        row["contributing_component_count"] = len(contributors)
    valid_aggregate_count = sum(row["aggregate_score"] is not None for row in comparisons)
    reliable = valid_aggregate_count >= config.min_valid_comparisons
    for row in comparisons:
        row["window_size_reliable"] = reliable
    return comparisons, {
        "overall_eligible_comparisons": len(comparisons),
        "valid_aggregate_comparisons": valid_aggregate_count,
        "reliable": reliable,
        "standardization": standardization,
    }


def rank_peaks(
    comparisons: Sequence[Mapping[str, Any]],
    *,
    window_minutes: int,
    min_separation_minutes: int,
    top_k: int,
) -> tuple[list[dict[str, Any]], int]:
    usable = [row for row in comparisons if row.get("aggregate_score") is not None]
    if not usable:
        return [], math.ceil(min_separation_minutes / window_minutes)
    peaks: list[dict[str, Any]] = []
    step = timedelta(minutes=window_minutes)
    for index, current in enumerate(usable):
        previous = usable[index - 1] if index > 0 and current["transition_timestamp"] - usable[index - 1]["transition_timestamp"] == step else None
        following = usable[index + 1] if index + 1 < len(usable) and usable[index + 1]["transition_timestamp"] - current["transition_timestamp"] == step else None
        score = current["aggregate_score"]
        greater_than_previous = previous is None or score > previous["aggregate_score"]
        at_least_following = following is None or score >= following["aggregate_score"]
        if greater_than_previous and at_least_following:
            peaks.append(dict(current))
    peaks.sort(key=lambda row: (-row["aggregate_score"], row["transition_timestamp"]))
    accepted: list[dict[str, Any]] = []
    for peak in peaks:
        if all(
            abs((peak["transition_timestamp"] - other["transition_timestamp"]).total_seconds()) >= min_separation_minutes * 60
            for other in accepted
        ):
            accepted.append(peak)
        if len(accepted) == top_k:
            break
    for rank, peak in enumerate(accepted, start=1):
        peak["rank"] = rank
    return accepted, math.ceil(min_separation_minutes / window_minutes)


def largest_distribution_changes(
    before: np.ndarray,
    after: np.ndarray,
    labels: Sequence[str],
    top_n: int,
) -> list[dict[str, Any]]:
    changes = [
        {"label": label, "before": float(before[index]), "after": float(after[index]), "delta": float(after[index] - before[index])}
        for index, label in enumerate(labels)
    ]
    return sorted(changes, key=lambda row: (-abs(row["delta"]), row["label"]))[:top_n]
