from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from swarm_lens.evidence_reconstruction.antecedents import _follow_through, classify_antecedent_support, rank_preceding_events
from swarm_lens.evidence_reconstruction.config import AntecedentConfig, AntecedentSupportConfig, PersistenceConfig, SemanticConfig, StructureConfig
from swarm_lens.evidence_reconstruction.logical_items import build_logical_items
from swarm_lens.evidence_reconstruction.semantics import build_semantic_space
from swarm_lens.evidence_reconstruction.structure import persistence_summary, specialization_summary, structural_summary
from swarm_lens.evidence_reconstruction.windows import reconstruction_intervals

UTC = timezone.utc


def _time(minutes: int) -> datetime:
    return datetime(2026, 5, 20, 12, 0, tzinfo=UTC) + timedelta(minutes=minutes)


def _semantic_config() -> SemanticConfig:
    return SemanticConfig(
        max_features=1000,
        ngram_min=1,
        ngram_max=2,
        min_df=1,
        background_quantile=0.95,
        threshold_floor=0.1,
        threshold_ceiling=0.9,
        fallback_threshold=0.2,
        min_source_pair_background_pairs=20,
        max_matches_per_preceding_event=5,
        max_markdown_matches_per_preceding_event=3,
    )


def _antecedent_config() -> AntecedentConfig:
    return AntecedentConfig(
        top_n=5,
        provisional_score_reference_threshold=0.5,
        minimum_available_components=3,
        uptake_agent_cap=3,
        novelty_weight=0.2,
        proximity_weight=0.2,
        distinct_agent_uptake_weight=0.2,
        detector_alignment_weight=0.2,
        persistence_weight=0.2,
    )


def _support_config() -> AntecedentSupportConfig:
    return AntecedentSupportConfig(
        moderate_min_fraction=0.4,
        strong_min_fraction=0.7,
        uptake_moderate_other_agents=1,
        uptake_strong_other_agents=3,
        alignment_moderate=0.25,
        alignment_strong=0.5,
        persistence_moderate=0.5,
        persistence_strong=0.75,
        novelty_moderate=0.5,
        novelty_strong=0.75,
    )


def _logical_item(item_id: str, minute: int, phase: str, agent: str, source: str, text: str) -> dict:
    return {
        "logical_item_id": item_id,
        "timestamp": _time(minute),
        "phase": phase,
        "relation": "before" if phase != "followup" else "after",
        "agent_id": agent,
        "agent_name": agent.upper(),
        "agent_model": "model",
        "speaker_type": "agent",
        "source_type": source,
        "event_kind": "computer_use_session_goal" if source == "session_goal" else "logical_chat",
        "action_type": None,
        "room_id": "room",
        "computer_use_session_id": f"session-{item_id}" if source == "session_goal" else None,
        "text": text,
        "provenance": [{"canonical_event_id": item_id, "source_table": "test", "source_row_id": item_id, "event_index": minute}],
    }


def test_linked_record_deduplication_and_provenance_retention() -> None:
    chat = {
        "canonical_event_id": "chat_messages:chat-1",
        "event_kind": "chat_message",
        "event_timestamp": _time(-5),
        "event_index": 10,
        "action_type": None,
        "agent_id": "agent-a",
        "agent_name": "Agent A",
        "agent_model": "model",
        "speaker_type": "agent",
        "speaker_name": "Agent A",
        "chat_content": "shared research plan",
        "session_goal": None,
        "event_content": None,
        "event_summary": None,
        "search_query": None,
        "search_answer": None,
        "room_id": "room",
        "computer_use_session_id": None,
        "linked_high_level_event_id": "event-1",
        "linked_high_level_event_index": 10,
        "source_table": "chat_messages",
        "source_row_id": "chat-1",
    }
    event = {
        **chat,
        "canonical_event_id": "events:event-1",
        "event_kind": "high_level_event",
        "event_timestamp": _time(-5) + timedelta(microseconds=1),
        "action_type": "AGENT_TALK",
        "chat_content": None,
        "event_content": "shared research plan",
        "linked_high_level_event_id": None,
        "source_table": "events",
        "source_row_id": "event-1",
    }
    items = build_logical_items(
        [event, chat],
        boundary=_time(0),
        start=_time(-30),
        end=_time(30),
        baseline_start=_time(-30),
        antecedent_start=_time(-15),
    )
    assert len(items) == 1
    assert items[0]["event_kind"] == "logical_chat"
    assert len(items[0]["provenance"]) == 2
    assert [row["canonical_event_id"] for row in items[0]["provenance"]] == ["chat_messages:chat-1", "events:event-1"]


def test_logical_items_are_temporally_ordered() -> None:
    base = {
        "event_kind": "computer_use_session_goal",
        "event_index": None,
        "action_type": None,
        "agent_id": "a",
        "agent_name": "A",
        "agent_model": "m",
        "speaker_type": None,
        "speaker_name": None,
        "chat_content": None,
        "session_goal": "goal",
        "event_content": None,
        "event_summary": None,
        "search_query": None,
        "search_answer": None,
        "room_id": None,
        "computer_use_session_id": "s",
        "linked_high_level_event_id": None,
        "linked_high_level_event_index": None,
        "source_table": "computer_use_sessions",
    }
    rows = [
        {**base, "canonical_event_id": "later", "source_row_id": "later", "event_timestamp": _time(5)},
        {**base, "canonical_event_id": "earlier", "source_row_id": "earlier", "event_timestamp": _time(-5)},
    ]
    items = build_logical_items(rows, boundary=_time(0), start=_time(-10), end=_time(10), baseline_start=_time(-10), antecedent_start=_time(-10))
    assert [row["logical_item_id"] for row in items] == ["earlier", "later"]


def test_semantic_fit_has_no_future_to_past_leakage_and_pair_fallback_is_recorded() -> None:
    items = [
        _logical_item("base", -20, "baseline", "a", "chat", "alpha baseline research"),
        _logical_item("pre", -5, "antecedent", "a", "chat", "novel alpha research plan"),
        _logical_item("future", 5, "followup", "b", "session_goal", "novel alpha research plan"),
    ]
    space = build_semantic_space(items, _semantic_config())
    assert space is not None
    assert "future" not in space.fit_item_ids
    assert space.thresholds["chat->session_goal"]["method"] == "common_threshold_fallback"


def test_inactivity_gap_clips_all_reconstruction_windows() -> None:
    interval = reconstruction_intervals(
        _time(0),
        episode_start=_time(-500),
        episode_end=_time(500),
        inactive_gaps=[{"start": _time(-180), "end": _time(-60)}, {"start": _time(45), "end": _time(300)}],
        antecedent_minutes=90,
        followup_minutes=120,
        baseline_minutes=120,
    )
    assert interval["antecedent_start"] == _time(-60)
    assert interval["followup_end"] == _time(45)
    assert interval["coverage_minutes"] == {"baseline": 0.0, "antecedent": 60.0, "followup": 45.0}


def test_persistence_calculation_distinguishes_runs_and_decay() -> None:
    persistent = persistence_summary([0, 1, 3], eligible_window_count=4, minimum_consecutive_windows=2)
    assert persistent["presence_windows"] == 3
    assert persistent["max_consecutive_windows"] == 2
    assert persistent["category"] == "persistent"
    decayed = persistence_summary([0], eligible_window_count=3, minimum_consecutive_windows=2)
    assert decayed["category"] == "decays_quickly"


def test_recurring_coactivity_is_not_conflated_with_same_room_overlap() -> None:
    windows = [
        {"phase": "antecedent", "active": True, "active_agents": ["a", "b"], "agent_event_counts": {"a": 2, "b": 1}, "room_agents": {"x": ["a"], "y": ["b"]}},
        {"phase": "antecedent", "active": True, "active_agents": ["a", "b"], "agent_event_counts": {"a": 1, "b": 2}, "room_agents": {"x": ["a", "b"]}},
        {"phase": "followup", "active": True, "active_agents": ["a"], "agent_event_counts": {"a": 1}, "room_agents": {"x": ["a"]}},
    ]
    config = StructureConfig(2, 3, 2, 2, 10, 10)
    summary = structural_summary(windows, config=config)
    coactivity = summary["antecedent"]["co_activity"]
    assert coactivity["recurring_same_window_pair_count"] == 1
    assert coactivity["recurring_pairs"][0]["same_window_count"] == 2
    assert coactivity["recurring_pairs"][0]["same_room_window_count"] == 1
    assert coactivity["recurring_same_room_pair_count"] == 0


def test_specialization_requires_repeated_qualified_windows() -> None:
    observations = [
        {"phase": "followup", "agent_id": "a", "agent_name": "A", "window_index": 0, "vector": [1.0, 0.0]},
        {"phase": "followup", "agent_id": "a", "agent_name": "A", "window_index": 0, "vector": [1.0, 0.0]},
        {"phase": "followup", "agent_id": "a", "agent_name": "A", "window_index": 1, "vector": [1.0, 0.0]},
        {"phase": "followup", "agent_id": "a", "agent_name": "A", "window_index": 1, "vector": [1.0, 0.0]},
    ]
    summary = specialization_summary(
        observations,
        labels=["one", "two"],
        eligible_windows_by_phase={"antecedent": 0, "followup": 2},
        config=StructureConfig(2, 3, 2, 2, 10, 10),
    )
    agent = summary["followup"]["agents"][0]
    assert agent["persistent_specialization"] is True
    assert agent["max_consecutive_windows_same_dominant_label"] == 2


def test_repeated_agent_and_multi_agent_follow_through_are_distinct() -> None:
    item = _logical_item("pre", -5, "antecedent", "a", "chat", "research plan")
    same_agent_match = {**_logical_item("s1", 5, "followup", "a", "session_goal", "research plan"), "similarity": 1.0}
    other_agent_match = {**_logical_item("s2", 6, "followup", "b", "session_goal", "research plan"), "similarity": 1.0}
    weak = _follow_through(item, [same_agent_match], [], followup_end=_time(30))
    multi = _follow_through(item, [same_agent_match, other_agent_match], [], followup_end=_time(30))
    assert weak["classification"] == "weak_follow_through"
    assert weak["other_agent_follow_through_count"] == 0
    assert multi["classification"] == "multi_agent_follow_through"
    assert multi["other_agent_follow_through_count"] == 1


def test_distinct_agent_uptake_ranking_is_deterministic_and_retains_provenance() -> None:
    items = [
        _logical_item("base", -40, "baseline", "z", "chat", "unrelated baseline material"),
        _logical_item("pre", -10, "antecedent", "a", "chat", "alpha replication research plan"),
        _logical_item("pre2", -8, "antecedent", "a", "chat", "different secondary note"),
        _logical_item("later-b", 2, "followup", "b", "session_goal", "alpha replication research plan"),
        _logical_item("later-c", 7, "followup", "c", "session_goal", "alpha replication research plan"),
    ]
    semantic_config = _semantic_config()
    space = build_semantic_space(items, semantic_config)
    assert space is not None
    changes = {
        "agent_ids": ["a", "b", "c", "z"],
        "action_types": ["CLICK"],
        "communication": {"delta": [0.5, -0.5]},
        "intention": {"delta": [0.5, -0.5]},
        "participation": {"delta": [0.1, 0.1, 0.1, -0.3]},
        "action_type": {"delta": [0.0]},
    }
    kwargs = dict(
        items=items,
        canonical_rows=[],
        boundary=_time(0),
        antecedent_start=_time(-30),
        followup_end=_time(30),
        followup_windows=[{"index": 0, "start": _time(0), "end": _time(15)}, {"index": 1, "start": _time(15), "end": _time(30)}],
        semantic_space=space,
        topic_vectors_by_item={"pre": [1.0, 0.0], "pre2": [0.0, 1.0]},
        stage2_changes=changes,
        antecedent_config=_antecedent_config(),
        antecedent_support_config=_support_config(),
        semantic_config=semantic_config,
        persistence_config=PersistenceConfig(2),
    )
    first = rank_preceding_events(**kwargs)
    second = rank_preceding_events(**kwargs)
    assert [row["logical_item_id"] for row in first] == [row["logical_item_id"] for row in second]
    pre = next(row for row in first if row["logical_item_id"] == "pre")
    assert pre["uptake"]["matching_other_agent_count"] == 2
    assert pre["behavioral_follow_through"]["classification"] == "multi_agent_follow_through"
    assert pre["provenance"][0]["canonical_event_id"] == "pre"


def test_top_ranked_preceding_events_retain_provisional_score_reference() -> None:
    config = _antecedent_config()
    assert config.top_n == 5
    assert config.provisional_score_reference_threshold == pytest.approx(0.5)


def test_antecedent_support_does_not_penalize_unavailable_novelty() -> None:
    without_novelty = classify_antecedent_support(
        matching_other_agent_count=3,
        follow_through_classification="multi_agent_follow_through",
        persistence_ratio=1.0,
        detector_alignment_score=0.6,
        novelty_score_value=None,
        config=_support_config(),
    )
    with_strong_novelty = classify_antecedent_support(
        matching_other_agent_count=3,
        follow_through_classification="multi_agent_follow_through",
        persistence_ratio=1.0,
        detector_alignment_score=0.6,
        novelty_score_value=0.8,
        config=_support_config(),
    )
    assert without_novelty[0] == "strong"
    assert with_strong_novelty[0] == "strong"
    assert without_novelty[1]["novelty_unavailable_not_penalized"] is True
    assert without_novelty[1]["support_fraction"] == pytest.approx(with_strong_novelty[1]["support_fraction"])
