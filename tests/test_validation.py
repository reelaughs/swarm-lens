from __future__ import annotations

from datetime import timezone

import pytest

from swarm_lens.ingestion import Episode, IngestionError, parse_timestamp
from swarm_lens.validation import validate_canonical_rows


def canonical_row(row_id: str, timestamp: str) -> dict:
    time = parse_timestamp(timestamp, field="test")
    return {
        "canonical_event_id": row_id,
        "event_timestamp": time,
        "village_goal_id": "goal-1",
        "village_goal_text": "Example",
        "source_row_number": 1,
        "source_record_sha256": "a" * 64,
        "agent_id": None,
        "agent_name": None,
        "agent_model": None,
        "room_id": None,
        "computer_use_session_id": None,
        "event_index": None,
        "chat_content": None,
        "session_goal": None,
        "event_content": None,
        "agent_goal_id": None,
        "source_table": "events",
        "event_kind": "high_level_event",
        "action_type": "WAIT",
    }


def episode() -> Episode:
    return Episode(
        "goal-1",
        "village-1",
        "Example",
        parse_timestamp("2026-01-01 00:00:00", field="start"),
        parse_timestamp("2026-01-03 00:00:00", field="end"),
        "example",
    )


def clean_audit() -> dict:
    return {
        "missing_chat_links": [],
        "missing_chat_links_episode": [],
        "missing_session_links": [],
        "missing_session_links_episode": [],
        "chat_mismatch_counts": {},
        "chat_mismatch_counts_episode": {},
        "chat_mismatch_examples_episode": [],
    }


def test_validation_checks_uniqueness() -> None:
    row = canonical_row("events:1", "2026-01-02 00:00:00")
    with pytest.raises(IngestionError, match="duplicate"):
        validate_canonical_rows([row, dict(row)], episode(), clean_audit())


def test_validation_checks_episode_bounds() -> None:
    row = canonical_row("events:1", "2026-01-03 00:00:00")
    with pytest.raises(IngestionError, match="outside episode"):
        validate_canonical_rows([row], episode(), clean_audit())


def test_validation_reports_optional_foreign_key_gaps_without_dropping_rows() -> None:
    row = canonical_row("events:1", "2026-01-02 00:00:00")
    audit = clean_audit()
    audit["missing_chat_links"] = ["missing"]
    audit["missing_chat_links_episode"] = ["missing"]
    result = validate_canonical_rows([row], episode(), audit)
    assert result["counts_by_source"]["events"] == 1


def test_validation_fails_on_episode_local_join_inconsistency() -> None:
    row = canonical_row("events:1", "2026-01-02 00:00:00")
    audit = clean_audit()
    audit["chat_mismatch_counts_episode"] = {"content": 1}
    audit["chat_mismatch_examples_episode"] = ["chat-1:content"]
    with pytest.raises(IngestionError, match="field consistency"):
        validate_canonical_rows([row], episode(), audit)
