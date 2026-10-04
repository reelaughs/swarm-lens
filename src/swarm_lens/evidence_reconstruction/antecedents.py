"""Transparent preceding-event ranking, uptake, and behavioral follow-through."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Mapping, Sequence

import numpy as np

from .config import AntecedentConfig, AntecedentSupportConfig, PersistenceConfig, SemanticConfig
from .semantics import SemanticSpace, later_semantic_matches, novelty_score
from .structure import persistence_summary


COMPONENTS = ("communication", "intention", "participation", "action_type")


def _support_points(value: float, moderate: float, strong: float) -> int:
    if value >= strong:
        return 2
    if value >= moderate:
        return 1
    return 0


def classify_antecedent_support(
    *,
    matching_other_agent_count: int,
    follow_through_classification: str,
    persistence_ratio: float | None,
    detector_alignment_score: float | None,
    novelty_score_value: float | None,
    config: AntecedentSupportConfig,
) -> tuple[str, dict[str, Any]]:
    """Describe observable support without asserting antecedent status or causation."""
    dimensions: dict[str, dict[str, Any]] = {
        "distinct_agent_uptake": {
            "available": True,
            "observed": matching_other_agent_count,
            "points": _support_points(
                float(matching_other_agent_count),
                float(config.uptake_moderate_other_agents),
                float(config.uptake_strong_other_agents),
            ),
            "moderate_threshold": config.uptake_moderate_other_agents,
            "strong_threshold": config.uptake_strong_other_agents,
        },
        "agent_level_behavioral_follow_through": {
            "available": True,
            "observed": follow_through_classification,
            "points": {
                "no_observable_follow_through": 0,
                "weak_follow_through": 1,
                "multi_agent_follow_through": 2,
            }[follow_through_classification],
            "moderate_threshold": "weak_follow_through",
            "strong_threshold": "multi_agent_follow_through",
        },
        "persistence": {
            "available": persistence_ratio is not None,
            "observed": persistence_ratio,
            "points": None
            if persistence_ratio is None
            else _support_points(persistence_ratio, config.persistence_moderate, config.persistence_strong),
            "moderate_threshold": config.persistence_moderate,
            "strong_threshold": config.persistence_strong,
        },
        "detector_alignment": {
            "available": detector_alignment_score is not None,
            "observed": detector_alignment_score,
            "points": None
            if detector_alignment_score is None
            else _support_points(detector_alignment_score, config.alignment_moderate, config.alignment_strong),
            "moderate_threshold": config.alignment_moderate,
            "strong_threshold": config.alignment_strong,
        },
        "novelty": {
            "available": novelty_score_value is not None,
            "observed": novelty_score_value,
            "points": None
            if novelty_score_value is None
            else _support_points(novelty_score_value, config.novelty_moderate, config.novelty_strong),
            "moderate_threshold": config.novelty_moderate,
            "strong_threshold": config.novelty_strong,
        },
    }
    available = [row for row in dimensions.values() if row["available"]]
    points_earned = sum(int(row["points"]) for row in available)
    points_available = 2 * len(available)
    fraction = points_earned / points_available if points_available else 0.0
    level = "strong" if fraction >= config.strong_min_fraction else "moderate" if fraction >= config.moderate_min_fraction else "limited"
    return level, {
        "support_fraction": fraction,
        "points_earned": points_earned,
        "points_available": points_available,
        "available_dimension_count": len(available),
        "novelty_unavailable_not_penalized": novelty_score_value is None,
        "dimensions": dimensions,
        "level_thresholds": {
            "moderate_min_fraction": config.moderate_min_fraction,
            "strong_min_fraction": config.strong_min_fraction,
        },
        "interpretation_constraint": "Descriptive support summarizes observable Stage 3 evidence and does not establish antecedent status or causation.",
    }


def _normalize(values: np.ndarray) -> np.ndarray | None:
    total = float(values.sum())
    return values / total if total > 0 else None


def stage2_distribution_changes(
    canonical_rows: Sequence[Mapping[str, Any]],
    candidate: Mapping[str, Any],
    topic_weights: Mapping[tuple[str, str], Sequence[float]],
    topic_labels: Mapping[str, Sequence[str]],
) -> dict[str, Any]:
    before_rows = [row for row in canonical_rows if candidate["before_window_start"] <= row["event_timestamp"] < candidate["before_window_end"]]
    after_rows = [row for row in canonical_rows if candidate["after_window_start"] <= row["event_timestamp"] < candidate["after_window_end"]]
    agent_ids = sorted({str(row["agent_id"]) for row in canonical_rows if row["event_kind"] == "high_level_event" and row.get("agent_id")})
    action_types = sorted({str(row["action_type"]) for row in canonical_rows if row["event_kind"] == "high_level_event" and row.get("action_type")})
    agent_names = {
        str(row["agent_id"]): row.get("agent_name") or str(row["agent_id"])
        for row in canonical_rows
        if row.get("agent_id")
    }

    def topic_distribution(rows: Sequence[Mapping[str, Any]], modality: str) -> np.ndarray | None:
        vectors = [np.asarray(topic_weights[(modality, row["canonical_event_id"])], dtype=float) for row in rows if (modality, row["canonical_event_id"]) in topic_weights]
        return _normalize(np.sum(vectors, axis=0)) if vectors else None

    def count_distribution(rows: Sequence[Mapping[str, Any]], field: str, vocabulary: Sequence[str]) -> np.ndarray | None:
        counts = Counter(str(row[field]) for row in rows if row.get(field))
        return _normalize(np.asarray([counts.get(value, 0) for value in vocabulary], dtype=float))

    distributions = {
        "communication": (
            topic_distribution([row for row in before_rows if row["event_kind"] == "chat_message" and row.get("speaker_type") == "agent"], "communication"),
            topic_distribution([row for row in after_rows if row["event_kind"] == "chat_message" and row.get("speaker_type") == "agent"], "communication"),
            list(topic_labels["communication"]),
        ),
        "intention": (
            topic_distribution([row for row in before_rows if row["event_kind"] == "computer_use_session_goal"], "intention"),
            topic_distribution([row for row in after_rows if row["event_kind"] == "computer_use_session_goal"], "intention"),
            list(topic_labels["intention"]),
        ),
        "participation": (
            count_distribution([row for row in before_rows if row["event_kind"] == "high_level_event"], "agent_id", agent_ids),
            count_distribution([row for row in after_rows if row["event_kind"] == "high_level_event"], "agent_id", agent_ids),
            [agent_names.get(value, value) for value in agent_ids],
        ),
        "action_type": (
            count_distribution([row for row in before_rows if row["event_kind"] == "high_level_event"], "action_type", action_types),
            count_distribution([row for row in after_rows if row["event_kind"] == "high_level_event"], "action_type", action_types),
            action_types,
        ),
    }
    result: dict[str, Any] = {"agent_ids": agent_ids, "action_types": action_types}
    for component, (before, after, labels) in distributions.items():
        delta = after - before if before is not None and after is not None else None
        result[component] = {
            "before": before.tolist() if before is not None else None,
            "after": after.tolist() if after is not None else None,
            "delta": delta.tolist() if delta is not None else None,
            "labels": labels,
        }
    return result


def detector_alignment(
    item: Mapping[str, Any],
    *,
    changes: Mapping[str, Any],
    topic_vector: Sequence[float] | None,
) -> tuple[float | None, list[dict[str, Any]]]:
    scores: list[dict[str, Any]] = []
    if item["source_type"] in {"chat", "user_talk"} and topic_vector is not None:
        delta = changes["communication"]["delta"]
        if delta is not None:
            positive = np.maximum(np.asarray(delta, dtype=float), 0)
            if positive.sum() > 0:
                direction = positive / positive.sum()
                scores.append({"component": "communication", "score": float(np.dot(np.asarray(topic_vector), direction))})
    if item["source_type"] == "session_goal" and topic_vector is not None:
        delta = changes["intention"]["delta"]
        if delta is not None:
            positive = np.maximum(np.asarray(delta, dtype=float), 0)
            if positive.sum() > 0:
                direction = positive / positive.sum()
                scores.append({"component": "intention", "score": float(np.dot(np.asarray(topic_vector), direction))})
    if item.get("agent_id") and changes["participation"]["delta"] is not None:
        try:
            index = changes["agent_ids"].index(str(item["agent_id"]))
        except ValueError:
            index = -1
        if index >= 0:
            positive = np.maximum(np.asarray(changes["participation"]["delta"], dtype=float), 0)
            maximum = float(positive.max()) if positive.size else 0.0
            scores.append({"component": "participation", "score": float(positive[index] / maximum) if maximum else 0.0})
    if item.get("action_type") and changes["action_type"]["delta"] is not None:
        try:
            index = changes["action_types"].index(str(item["action_type"]))
        except ValueError:
            index = -1
        if index >= 0:
            positive = np.maximum(np.asarray(changes["action_type"]["delta"], dtype=float), 0)
            maximum = float(positive.max()) if positive.size else 0.0
            scores.append({"component": "action_type", "score": float(positive[index] / maximum) if maximum else 0.0})
    return (float(np.mean([row["score"] for row in scores])) if scores else None), scores


def _window_index(timestamp: datetime, windows: Sequence[Mapping[str, Any]]) -> int | None:
    for window in windows:
        if window["start"] <= timestamp < window["end"]:
            return int(window["index"])
    return None


def _follow_through(
    item: Mapping[str, Any],
    matches: Sequence[Mapping[str, Any]],
    canonical_rows: Sequence[Mapping[str, Any]],
    *,
    followup_end: datetime,
) -> dict[str, Any]:
    uptake_agents = {str(match["agent_id"]) for match in matches if match.get("agent_id")}
    qualifying = [match for match in matches if match["source_type"] in {"session_goal", "high_level_action"} and match.get("agent_id")]
    linked_actions = []
    session_ids = {match["computer_use_session_id"] for match in qualifying if match["source_type"] == "session_goal" and match.get("computer_use_session_id")}
    for row in canonical_rows:
        if (
            row["event_kind"] == "high_level_event"
            and row.get("computer_use_session_id") in session_ids
            and row.get("agent_id")
            and item["timestamp"] < row["event_timestamp"] < followup_end
            and row.get("action_type") not in {"AGENT_TALK", "USER_TALK"}
        ):
            linked_actions.append(
                {
                    "timestamp": row["event_timestamp"],
                    "agent_id": row["agent_id"],
                    "agent_name": row.get("agent_name"),
                    "action_type": row.get("action_type"),
                    "computer_use_session_id": row.get("computer_use_session_id"),
                    "provenance": [
                        {
                            "canonical_event_id": row["canonical_event_id"],
                            "source_table": row["source_table"],
                            "source_row_id": row["source_row_id"],
                            "event_index": row.get("event_index"),
                        }
                    ],
                }
            )
    follow_agents = {str(match["agent_id"]) for match in qualifying if match.get("agent_id")}
    follow_agents.update(str(row["agent_id"]) for row in linked_actions)
    if len(follow_agents) >= 2:
        classification = "multi_agent_follow_through"
    elif follow_agents:
        classification = "weak_follow_through"
    else:
        classification = "no_observable_follow_through"
    origin = str(item.get("agent_id")) if item.get("agent_id") else None
    return {
        "classification": classification,
        "semantic_uptake_agent_count": len(uptake_agents),
        "qualifying_follow_through_agent_count": len(follow_agents),
        "follow_through_agents_over_semantic_uptake_agents": f"{len(follow_agents)}/{len(uptake_agents)}",
        "qualifying_agent_ids": sorted(follow_agents),
        "other_agent_follow_through_count": len({value for value in follow_agents if value != origin}),
        "qualifying_semantic_matches": list(qualifying),
        "linked_action_count": len(linked_actions),
        "linked_actions": linked_actions,
        "rule": "Communication similarity alone does not qualify; a matching session goal, text-bearing high-level activity, or activity linked to a matching session is required.",
    }


def rank_preceding_events(
    *,
    items: Sequence[Mapping[str, Any]],
    canonical_rows: Sequence[Mapping[str, Any]],
    boundary: datetime,
    antecedent_start: datetime,
    followup_end: datetime,
    followup_windows: Sequence[Mapping[str, Any]],
    semantic_space: SemanticSpace | None,
    topic_vectors_by_item: Mapping[str, Sequence[float]],
    stage2_changes: Mapping[str, Any],
    antecedent_config: AntecedentConfig,
    antecedent_support_config: AntecedentSupportConfig,
    semantic_config: SemanticConfig,
    persistence_config: PersistenceConfig,
) -> list[dict[str, Any]]:
    baseline_items = [item for item in items if item["phase"] == "baseline"]
    later_items = [item for item in items if item["phase"] in {"antecedent", "followup"} and item.get("text")]
    eligible = [
        item
        for item in items
        if item["phase"] == "antecedent"
        and (item["source_type"] in {"chat", "user_talk", "session_goal"} or bool(item.get("text")))
    ]
    rows = []
    for item in eligible:
        novelty, novelty_match = novelty_score(item, baseline_items, semantic_space)
        minutes_before = max(0.0, (boundary - item["timestamp"]).total_seconds() / 60)
        antecedent_duration = max(1.0, (boundary - antecedent_start).total_seconds() / 60)
        proximity = max(0.0, min(1.0, 1.0 - minutes_before / antecedent_duration))
        all_matches, match_coverage = later_semantic_matches(
            item,
            later_items,
            semantic_space,
            maximum_matches=max(len(later_items), 1),
        )
        origin = str(item.get("agent_id")) if item.get("agent_id") else None
        other_agents = sorted({str(match["agent_id"]) for match in all_matches if match.get("agent_id") and str(match["agent_id"]) != origin})
        uptake = min(1.0, len(other_agents) / antecedent_config.uptake_agent_cap)
        alignment, alignment_details = detector_alignment(
            item,
            changes=stage2_changes,
            topic_vector=topic_vectors_by_item.get(item["logical_item_id"]),
        )
        presence_indices = sorted(
            {
                index
                for match in all_matches
                if match["phase"] == "followup"
                for index in [_window_index(match["timestamp"], followup_windows)]
                if index is not None
            }
        )
        persistence = persistence_summary(
            presence_indices,
            eligible_window_count=len(followup_windows),
            minimum_consecutive_windows=persistence_config.minimum_consecutive_windows,
        )
        persistence_score = persistence["persistence_ratio"]
        components = {
            "novelty": novelty,
            "proximity": proximity,
            "distinct_agent_uptake": uptake,
            "detector_alignment": alignment,
            "persistence": persistence_score,
        }
        available = [name for name, value in components.items() if value is not None]
        available_weight = sum(antecedent_config.weights[name] for name in available)
        aggregate = (
            sum(antecedent_config.weights[name] * float(components[name]) for name in available) / available_weight
            if len(available) >= antecedent_config.minimum_available_components and available_weight > 0
            else None
        )
        retained_matches = all_matches[: semantic_config.max_matches_per_preceding_event]
        follow_through = _follow_through(item, all_matches, canonical_rows, followup_end=followup_end)
        distinct_match_agents = {str(match["agent_id"]) for match in all_matches if match.get("agent_id")}
        support_level, support_details = classify_antecedent_support(
            matching_other_agent_count=len(other_agents),
            follow_through_classification=follow_through["classification"],
            persistence_ratio=persistence_score,
            detector_alignment_score=alignment,
            novelty_score_value=novelty,
            config=antecedent_support_config,
        )
        rows.append(
            {
                "logical_item_id": item["logical_item_id"],
                "timestamp": item["timestamp"],
                "minutes_before_boundary": minutes_before,
                "agent_id": item.get("agent_id"),
                "agent_name": item.get("agent_name"),
                "source_type": item["source_type"],
                "event_kind": item["event_kind"],
                "action_type": item.get("action_type"),
                "room_id": item.get("room_id"),
                "text": item.get("text"),
                "provenance": item["provenance"],
                "score_components": components,
                "available_score_components": available,
                "available_weight": available_weight,
                "aggregate_score": aggregate,
                "provisional_score_reference_threshold": antecedent_config.provisional_score_reference_threshold,
                "above_provisional_score_reference": aggregate is not None
                and aggregate >= antecedent_config.provisional_score_reference_threshold,
                "evidence_label": "ranked_preceding_evidence",
                "antecedent_support": support_level,
                "antecedent_support_details": support_details,
                "novelty_nearest_baseline_match": novelty_match,
                "population_level_alignment": {
                    "score": alignment,
                    "component_details": alignment_details,
                    "does_not_establish_agent_level_follow_through": True,
                },
                "uptake": {
                    "matching_item_count": match_coverage["matched_items"],
                    "eligible_later_text_item_count": match_coverage["eligible_later_text_items"],
                    "matching_distinct_agent_count": len(distinct_match_agents),
                    "matching_other_agent_count": len(other_agents),
                    "active_agent_denominator": len({str(value.get("agent_id")) for value in items if value.get("agent_id")}),
                    "matching_agents_over_active_agents": f"{len(distinct_match_agents)}/{len({str(value.get('agent_id')) for value in items if value.get('agent_id')})}",
                    "other_agent_ids": other_agents,
                    "highest_scoring_matches": retained_matches,
                    "retained_match_count": len(retained_matches),
                },
                "behavioral_follow_through": follow_through,
                "persistence": {
                    **persistence,
                    "expanded_across_agents": len(other_agents) >= 2,
                    "distinct_later_other_agents": len(other_agents),
                },
            }
        )
    rows.sort(
        key=lambda row: (
            row["aggregate_score"] is None,
            -(row["aggregate_score"] or 0.0),
            row["timestamp"],
            row["logical_item_id"],
        )
    )
    for index, row in enumerate(rows, start=1):
        row["preceding_event_rank"] = index
    return rows[: antecedent_config.top_n]


def candidate_component_scores(candidate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        component: {
            "js_divergence": candidate.get(f"{component}_js"),
            "standardized_score": candidate.get(f"{component}_z"),
            "eligible": candidate.get(f"{component}_eligible"),
            "largest_changes": json.loads(candidate[f"{component}_changes_json"]),
        }
        for component in COMPONENTS
    }
