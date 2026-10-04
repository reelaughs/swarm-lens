"""Neutral structural observations: co-activity, concentration, and specialization."""

from __future__ import annotations

import itertools
import math
import re
from collections import Counter, defaultdict
from statistics import fmean
from typing import Any, Mapping, Sequence

import numpy as np

from swarm_lens.turning_points.distributions import js_divergence

from .config import StructureConfig
from .windows import make_subwindows


def _agent_key(row: Mapping[str, Any]) -> str | None:
    value = row.get("agent_id") or row.get("agent_name")
    return str(value) if value else None


def persistence_summary(
    presence_window_indices: Sequence[int],
    *,
    eligible_window_count: int,
    minimum_consecutive_windows: int,
) -> dict[str, Any]:
    present = sorted(set(int(value) for value in presence_window_indices))
    longest = 0
    current = 0
    previous = None
    for value in present:
        current = current + 1 if previous is not None and value == previous + 1 else 1
        longest = max(longest, current)
        previous = value
    if eligible_window_count < 2:
        category = "insufficient_evidence"
    elif len(present) <= 1:
        category = "single_appearance" if present else "not_observed"
    elif longest >= minimum_consecutive_windows:
        category = "persistent"
    else:
        category = "intermittent"
    decays_quickly = bool(present and present[0] == 0 and 1 not in present and eligible_window_count >= 2)
    return {
        "presence_windows": len(present),
        "eligible_windows": eligible_window_count,
        "persistence_ratio": len(present) / eligible_window_count if eligible_window_count else None,
        "max_consecutive_windows": longest,
        "category": "decays_quickly" if decays_quickly else category,
        "window_indices": present,
    }


def build_structural_windows(
    canonical_rows: Sequence[Mapping[str, Any]],
    *,
    antecedent_start: Any,
    boundary: Any,
    followup_end: Any,
    minutes: int,
) -> list[dict[str, Any]]:
    windows = []
    for phase, start, end in (("antecedent", antecedent_start, boundary), ("followup", boundary, followup_end)):
        for definition in make_subwindows(start, end, minutes):
            event_rows = [
                row
                for row in canonical_rows
                if row["event_kind"] == "high_level_event"
                and row.get("agent_id")
                and definition["start"] <= row["event_timestamp"] < definition["end"]
            ]
            agents = sorted({_agent_key(row) for row in event_rows if _agent_key(row)})
            room_agents: dict[str, set[str]] = defaultdict(set)
            for row in event_rows:
                if row.get("room_id") and _agent_key(row):
                    room_agents[str(row["room_id"])].add(str(_agent_key(row)))
            windows.append(
                {
                    **definition,
                    "phase": phase,
                    "active": bool(event_rows),
                    "high_level_event_count": len(event_rows),
                    "active_agents": agents,
                    "distinct_active_agents": len(agents),
                    "agent_event_counts": dict(Counter(str(_agent_key(row)) for row in event_rows if _agent_key(row))),
                    "room_agents": {room: sorted(values) for room, values in sorted(room_agents.items())},
                }
            )
    return windows


def _concentration(windows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    for window in windows:
        counts.update(window["agent_event_counts"])
    total = sum(counts.values())
    if not total:
        return {
            "high_level_event_count": 0,
            "distinct_active_agents": 0,
            "agent_activity_shares": {},
            "hhi": None,
            "normalized_entropy": None,
            "effective_agent_count": None,
        }
    shares = {agent: count / total for agent, count in sorted(counts.items())}
    hhi = sum(value * value for value in shares.values())
    entropy = -sum(value * math.log(value) for value in shares.values() if value > 0)
    normalized_entropy = entropy / math.log(len(shares)) if len(shares) > 1 else 0.0
    return {
        "high_level_event_count": total,
        "distinct_active_agents": len(shares),
        "agent_activity_shares": shares,
        "hhi": hhi,
        "normalized_entropy": normalized_entropy,
        "effective_agent_count": 1.0 / hhi if hhi else None,
    }


def _recurring_groups(
    windows: Sequence[Mapping[str, Any]],
    *,
    minimum_windows: int,
    maximum_set_size: int,
    maximum_reported_pairs: int,
    maximum_reported_sets: int,
) -> dict[str, Any]:
    active_windows = [window for window in windows if window["active"]]
    all_agents = sorted({agent for window in active_windows for agent in window["active_agents"]})
    pair_support: Counter[tuple[str, str]] = Counter()
    room_pair_support: Counter[tuple[str, str]] = Counter()
    set_support: Counter[tuple[str, ...]] = Counter()
    agent_window_support: Counter[str] = Counter()
    for window in active_windows:
        agents = list(window["active_agents"])
        agent_window_support.update(agents)
        for pair in itertools.combinations(agents, 2):
            pair_support[pair] += 1
        room_pairs: set[tuple[str, str]] = set()
        for room_agents in window["room_agents"].values():
            room_pairs.update(itertools.combinations(room_agents, 2))
        room_pair_support.update(room_pairs)
        for size in range(2, min(maximum_set_size, len(agents)) + 1):
            set_support.update(itertools.combinations(agents, size))
    pair_rows = []
    for pair, support in pair_support.items():
        if support < minimum_windows:
            continue
        union = agent_window_support[pair[0]] + agent_window_support[pair[1]] - support
        pair_rows.append(
            {
                "agents": list(pair),
                "same_window_count": support,
                "eligible_active_windows": len(active_windows),
                "pair_union_windows": union,
                "same_window_jaccard": support / union if union else None,
                "same_room_window_count": room_pair_support[pair],
            }
        )
    pair_rows.sort(key=lambda row: (-row["same_window_count"], -row["same_room_window_count"], row["agents"]))
    set_rows = [
        {"agents": list(group), "same_window_count": support, "eligible_active_windows": len(active_windows)}
        for group, support in set_support.items()
        if len(group) > 2 and support >= minimum_windows
    ]
    set_rows.sort(key=lambda row: (-row["same_window_count"], -len(row["agents"]), row["agents"]))
    eligible_pairs = len(all_agents) * (len(all_agents) - 1) // 2
    return {
        "active_windows": len(active_windows),
        "distinct_agents": len(all_agents),
        "eligible_agent_pairs": eligible_pairs,
        "recurring_same_window_pair_count": len(pair_rows),
        "recurring_same_room_pair_count": sum(row["same_room_window_count"] >= minimum_windows for row in pair_rows),
        "recurring_pairs": pair_rows[:maximum_reported_pairs],
        "recurring_pair_records_retained": min(len(pair_rows), maximum_reported_pairs),
        "recurring_larger_sets": set_rows[:maximum_reported_sets],
        "recurring_larger_set_records_retained": min(len(set_rows), maximum_reported_sets),
        "evidence_role": "activity_density_context",
        "relational_evidence": False,
        "terminology_note": "Same-window co-activity is an activity-density/context measure. Same-room overlap is a locational coincidence. Neither is relational evidence or may independently support a later social-process interpretation.",
    }


def explicit_address_edges(items: Sequence[Mapping[str, Any]], known_agents: Mapping[str, str]) -> dict[str, Any]:
    edges = []
    for item in items:
        if item["source_type"] not in {"chat", "user_talk"} or not item.get("text"):
            continue
        sender = _agent_key(item)
        text = str(item["text"])
        for agent_id, agent_name in known_agents.items():
            if sender == agent_id:
                continue
            pattern = re.compile(r"(?<![\w.-])@" + re.escape(agent_name) + r"(?![\w.-])", re.IGNORECASE)
            if pattern.search(text):
                edges.append(
                    {
                        "timestamp": item["timestamp"],
                        "source_agent_id": sender,
                        "source_agent_name": item.get("agent_name"),
                        "addressed_agent_id": agent_id,
                        "addressed_agent_name": agent_name,
                        "logical_item_id": item["logical_item_id"],
                        "provenance": item["provenance"],
                    }
                )
    edges.sort(key=lambda row: (row["timestamp"], row["logical_item_id"], row["addressed_agent_id"]))
    return {"explicit_address_edge_count": len(edges), "edges": edges}


def structural_summary(
    structural_windows: Sequence[Mapping[str, Any]],
    *,
    config: StructureConfig,
) -> dict[str, Any]:
    result = {}
    for phase in ("antecedent", "followup"):
        windows = [window for window in structural_windows if window["phase"] == phase]
        result[phase] = {
            "window_count": len(windows),
            "active_window_count": sum(window["active"] for window in windows),
            "concentration": _concentration(windows),
            "co_activity": _recurring_groups(
                windows,
                minimum_windows=config.minimum_recurring_windows,
                maximum_set_size=config.maximum_recurring_set_size,
                maximum_reported_pairs=config.maximum_reported_pairs,
                maximum_reported_sets=config.maximum_reported_sets,
            ),
        }
    before = result["antecedent"]["concentration"]
    after = result["followup"]["concentration"]
    result["changes"] = {
        "hhi_delta": after["hhi"] - before["hhi"] if before["hhi"] is not None and after["hhi"] is not None else None,
        "normalized_entropy_delta": after["normalized_entropy"] - before["normalized_entropy"]
        if before["normalized_entropy"] is not None and after["normalized_entropy"] is not None
        else None,
        "effective_agent_count_delta": after["effective_agent_count"] - before["effective_agent_count"]
        if before["effective_agent_count"] is not None and after["effective_agent_count"] is not None
        else None,
    }
    return result


def _normalized_entropy(distribution: np.ndarray) -> float:
    positive = distribution[distribution > 0]
    if len(distribution) <= 1 or not len(positive):
        return 0.0
    return float(-np.sum(positive * np.log(positive)) / np.log(len(distribution)))


def specialization_summary(
    observations: Sequence[Mapping[str, Any]],
    *,
    labels: Sequence[str],
    eligible_windows_by_phase: Mapping[str, int],
    config: StructureConfig,
) -> dict[str, Any]:
    """Summarize agent-specific distributions without assigning social roles."""
    result: dict[str, Any] = {}
    for phase in ("antecedent", "followup"):
        phase_rows = [row for row in observations if row["phase"] == phase]
        by_agent: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for row in phase_rows:
            if row.get("agent_id"):
                by_agent[str(row["agent_id"])].append(row)
        agents = []
        qualified_distributions = []
        for agent_id, rows in sorted(by_agent.items()):
            observation_count = len(rows)
            vector = np.sum([np.asarray(row["vector"], dtype=float) for row in rows], axis=0)
            total = float(vector.sum())
            distribution = vector / total if total > 0 else vector
            qualified = observation_count >= config.minimum_specialization_observations and total > 0
            dominant_index = int(np.argmax(distribution)) if qualified else None
            by_window: dict[int, list[np.ndarray]] = defaultdict(list)
            for row in rows:
                by_window[int(row["window_index"])].append(np.asarray(row["vector"], dtype=float))
            dominant_by_window = {}
            for index, vectors in sorted(by_window.items()):
                if len(vectors) < config.minimum_specialization_observations:
                    continue
                summed = np.sum(vectors, axis=0)
                if summed.sum() > 0:
                    dominant_by_window[index] = int(np.argmax(summed))
            longest = 0
            current = 0
            previous_index = None
            previous_label = None
            for index, label_index in dominant_by_window.items():
                current = current + 1 if previous_index is not None and index == previous_index + 1 and label_index == previous_label else 1
                longest = max(longest, current)
                previous_index = index
                previous_label = label_index
            agent_row = {
                "agent_id": agent_id,
                "agent_name": rows[0].get("agent_name"),
                "observation_count": observation_count,
                "minimum_required_observations": config.minimum_specialization_observations,
                "qualified": qualified,
                "distribution": distribution.tolist() if total > 0 else None,
                "dominant_label": labels[dominant_index] if dominant_index is not None else None,
                "dominant_share": float(distribution[dominant_index]) if dominant_index is not None else None,
                "specialization_index": 1.0 - _normalized_entropy(distribution) if qualified else None,
                "qualified_windows": len(dominant_by_window),
                "eligible_windows": eligible_windows_by_phase.get(phase, 0),
                "max_consecutive_windows_same_dominant_label": longest,
                "persistent_specialization": longest >= config.minimum_specialization_windows,
            }
            agents.append(agent_row)
            if qualified:
                qualified_distributions.append(distribution)
        pairwise = []
        for left, right in itertools.combinations(qualified_distributions, 2):
            pairwise.append(js_divergence(left, right))
        result[phase] = {
            "agent_count_observed": len(by_agent),
            "agent_count_qualified": len(qualified_distributions),
            "eligible_agent_pairs": len(qualified_distributions) * (len(qualified_distributions) - 1) // 2,
            "mean_pairwise_js_divergence": fmean(pairwise) if pairwise else None,
            "agents": agents,
        }
    return result
