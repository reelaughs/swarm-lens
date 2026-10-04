from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from swarm_lens.turning_points.config import DetectorConfig
from swarm_lens.turning_points.distributions import aggregate_available, js_divergence, normalize_distribution, robust_standardize
from swarm_lens.turning_points.scoring import rank_peaks, score_window_size
from swarm_lens.turning_points.topics import TopicRepresentation
from swarm_lens.turning_points.windowing import Window, eligible_adjacent_pairs, inactive_gaps

UTC = timezone.utc


def detector_config(**overrides: int) -> DetectorConfig:
    values = {
        "window_sizes_minutes": (30, 60, 90),
        "overall_min_high_level_events": 4,
        "overall_min_distinct_agents": 2,
        "communication_min_documents_per_window": 3,
        "intention_min_documents_per_window": 2,
        "participation_min_agent_events_per_window": 4,
        "participation_min_distinct_agents": 2,
        "action_type_min_events_per_window": 4,
        "min_components_for_aggregate": 3,
        "min_valid_comparisons": 10,
        "min_peak_separation_minutes": 120,
        "top_k": 5,
        "top_changes": 5,
        "random_seed": 42,
    }
    values.update(overrides)
    return DetectorConfig(**values)


def event(row_id: str, agent: str, action: str = "WAIT") -> dict:
    return {"canonical_event_id": row_id, "agent_id": agent, "action_type": action}


def test_distribution_normalization() -> None:
    result = normalize_distribution([2, 3, 5])
    assert result is not None
    assert result.sum() == pytest.approx(1.0)
    assert result.tolist() == pytest.approx([0.2, 0.3, 0.5])
    assert normalize_distribution([0, 0]) is None
    with pytest.raises(ValueError):
        normalize_distribution([1, -1])


def test_jensen_shannon_known_values() -> None:
    assert js_divergence([0.5, 0.5], [0.5, 0.5]) == pytest.approx(0.0)
    assert js_divergence([1, 0], [0, 1]) == pytest.approx(1.0)


def test_inactive_gap_is_not_bridged() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    windows = [Window(i, start + timedelta(hours=i), start + timedelta(hours=i + 1)) for i in range(3)]
    for index in (0, 2):
        rows = [event(f"e{index}-{i}", f"a{i % 2}") for i in range(4)]
        windows[index].event_rows.extend(rows)
        windows[index].agent_event_rows.extend(rows)
    assert eligible_adjacent_pairs(windows, min_events=4, min_agents=2) == []
    gaps = inactive_gaps(windows, 60)
    assert len(gaps) == 1
    assert gaps[0]["duration_minutes"] == 60


def test_underpowered_modality_is_null_without_dropping_comparison() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    windows = [Window(i, start + timedelta(hours=i), start + timedelta(hours=i + 1)) for i in range(2)]
    communication_weights = {}
    intention_weights = {}
    for window_index, window in enumerate(windows):
        events = [event(f"e{window_index}-{i}", f"a{i % 2}", "WAIT" if i < 2 else "AGENT_TALK") for i in range(4)]
        window.event_rows.extend(events)
        window.agent_event_rows.extend(events)
        for i in range(2):
            row_id = f"c{window_index}-{i}"
            row = {"canonical_event_id": row_id}
            window.agent_chat_rows.append(row)
            communication_weights[row_id] = np.array([0.8, 0.2])
        for i in range(2):
            row_id = f"s{window_index}-{i}"
            row = {"canonical_event_id": row_id}
            window.session_rows.append(row)
            intention_weights[row_id] = np.array([0.4, 0.6])
    communication = TopicRepresentation("communication", communication_weights, ["c1", "c2"], {})
    intention = TopicRepresentation("intention", intention_weights, ["i1", "i2"], {})
    comparisons, _ = score_window_size(
        windows,
        window_minutes=60,
        config=detector_config(),
        communication=communication,
        intention=intention,
        agent_vocabulary=["a0", "a1"],
        action_vocabulary=["AGENT_TALK", "WAIT"],
    )
    assert len(comparisons) == 1
    assert comparisons[0]["communication_js"] is None
    assert comparisons[0]["intention_js"] == pytest.approx(0.0)
    assert comparisons[0]["participation_js"] == pytest.approx(0.0)
    assert comparisons[0]["action_type_js"] == pytest.approx(0.0)


def test_minimum_valid_comparisons_and_three_of_four_aggregate() -> None:
    standardized, metadata = robust_standardize([float(i) for i in range(9)], min_valid=10)
    assert standardized == [None] * 9
    assert metadata["reliable"] is False
    standardized, metadata = robust_standardize([float(i) for i in range(10)], min_valid=10)
    assert metadata["reliable"] is True
    assert all(value is not None for value in standardized)
    aggregate, contributors = aggregate_available(
        {"communication": None, "intention": 1.0, "participation": 2.0, "action_type": 3.0},
        minimum_components=3,
    )
    assert aggregate == pytest.approx(2.0)
    assert contributors == ("intention", "participation", "action_type")


def test_candidate_ranking_is_deterministic_and_uses_clock_separation() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    scores = [0.0, 5.0, 1.0, 4.0, 0.0, 3.0]
    rows = [
        {"comparison_id": str(i), "transition_timestamp": start + timedelta(minutes=30 * i), "aggregate_score": score}
        for i, score in enumerate(scores)
    ]
    first, steps = rank_peaks(rows, window_minutes=30, min_separation_minutes=120, top_k=5)
    second, _ = rank_peaks(rows, window_minutes=30, min_separation_minutes=120, top_k=5)
    assert steps == 4
    assert [row["comparison_id"] for row in first] == [row["comparison_id"] for row in second]
    assert [row["comparison_id"] for row in first] == ["1", "5"]
