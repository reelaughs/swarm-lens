from __future__ import annotations

import gzip
import hashlib
import json
from datetime import timezone
from pathlib import Path

import pytest

from swarm_lens.ingestion import (
    Episode,
    IngestionError,
    _active_agent_goal,
    _require_unique,
    build_episode,
    collect_episode,
    iter_raw_rows,
    parse_timestamp,
    resolve_episode,
    safe_slug,
)


def write_gzip_rows(path: Path, rows: list[dict]) -> list[bytes]:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = [json.dumps(row, separators=(",", ":")).encode() for row in rows]
    with gzip.open(path, "wb") as stream:
        for line in encoded:
            stream.write(line + b"\n")
    return encoded


def village_goal(goal_id: str = "goal-1", goal: str = "Perform novel research!") -> dict:
    return {
        "id": goal_id,
        "village_id": "village-1",
        "goal": goal,
        "start_time": "2026-05-11 07:47:04.725",
        "end_time": "2026-05-18 12:26:24.346",
        "created_at": "2026-05-11 07:47:04.725001",
        "updated_at": "2026-05-18 12:26:24.346001",
    }


def test_timestamp_parsing_is_strict_utc() -> None:
    value = parse_timestamp("2026-05-11 07:47:04.725123", field="test")
    assert value.tzinfo == timezone.utc
    assert value.microsecond == 725123
    with pytest.raises(IngestionError, match="timezone"):
        parse_timestamp("2026-05-11T07:47:04+00:00", field="test")
    with pytest.raises(IngestionError, match="invalid timestamp"):
        parse_timestamp("not-a-time", field="test")


def test_episode_filter_is_half_open() -> None:
    episode = Episode(
        id="goal-1",
        village_id="village-1",
        goal="Example",
        start=parse_timestamp("2026-01-01 00:00:00", field="start"),
        end=parse_timestamp("2026-01-02 00:00:00", field="end"),
        slug="example",
    )
    assert episode.contains(episode.start)
    assert not episode.contains(episode.end)


def test_resolve_episode_by_name_and_id_and_slug_collision(tmp_path: Path) -> None:
    rows = [village_goal(), village_goal("goal-2", "Perform novel research?")]
    rows[1]["start_time"] = "2026-06-01 00:00:00"
    rows[1]["end_time"] = None
    write_gzip_rows(tmp_path / "village_goals.jsonl.gz", rows)
    by_name = resolve_episode(tmp_path, goal="Perform novel research!")
    by_id = resolve_episode(tmp_path, goal_id="goal-1")
    assert by_name == by_id
    assert by_name.slug == "perform-novel-research-goal-1"
    assert safe_slug("Perform novel research!") == "perform-novel-research"


def test_exact_goal_name_must_be_unique(tmp_path: Path) -> None:
    write_gzip_rows(tmp_path / "village_goals.jsonl.gz", [village_goal(), village_goal("goal-2")])
    with pytest.raises(IngestionError, match="found 2"):
        resolve_episode(tmp_path, goal="Perform novel research!")


def test_duplicate_ids_fail() -> None:
    class Stub:
        record = {"id": "same"}

    with pytest.raises(IngestionError, match="duplicate"):
        _require_unique([Stub(), Stub()], "example")


def test_overlapping_agent_goals_fail() -> None:
    class Stub:
        def __init__(self, goal_id: str) -> None:
            self.record = {"id": goal_id}

    start = parse_timestamp("2026-01-01 00:00:00", field="start")
    when = parse_timestamp("2026-01-02 00:00:00", field="when")
    goals = {"agent-1": [(Stub("a"), start, None), (Stub("b"), start, None)]}
    with pytest.raises(IngestionError, match="overlapping"):
        _active_agent_goal(goals, "agent-1", when)


def test_provenance_hash_recovers_original_json_bytes(tmp_path: Path) -> None:
    rows = [village_goal()]
    encoded = write_gzip_rows(tmp_path / "village_goals.jsonl.gz", rows)
    raw = next(iter_raw_rows(tmp_path, "village_goals"))
    assert raw.row_number == 1
    assert raw.record == rows[0]
    assert raw.sha256 == hashlib.sha256(encoded[0]).hexdigest()


def test_generic_build_joins_sources_and_writes_episode_outputs(tmp_path: Path) -> None:
    raw_dir = tmp_path / "data" / "raw"
    agent = {
        "id": "agent-1",
        "name": "Test Agent",
        "model_string": "test-model",
        "village_id": "village-1",
        "created_at": "2025-12-01 00:00:00",
        "updated_at": "2025-12-01 00:00:00",
    }
    agent_goal = {
        "id": "agent-goal-1",
        "agent_id": "agent-1",
        "name": "Test individual goal",
        "short_name": "Test",
        "description": "Exercise the temporal join",
        "start_time": "2026-05-11 00:00:00",
        "end_time": "2026-05-12 00:00:00",
        "created_at": "2026-05-10 00:00:00",
        "updated_at": "2026-05-10 00:00:00",
    }
    chat = {
        "id": "chat-1",
        "agent_speaker_id": "agent-1",
        "user_speaker_id": None,
        "speaker_type": "agent",
        "content": "A test message",
        "room_id": "room-1",
        "created_at": "2026-05-11 08:00:00.000001",
        "updated_at": "2026-05-11 08:00:00.000001",
        "has_been_approved": None,
    }
    session = {
        "id": "session-1",
        "agent_id": "agent-1",
        "village_id": "village-1",
        "session_goal": "Test the session join",
        "short_displayed_session_goal": "Test join",
        "created_at": "2026-05-11 08:10:00",
        "updated_at": "2026-05-11 08:10:00",
        "has_been_asked_to_stop": False,
    }
    events = [
        {
            "id": "event-1",
            "event_index": 10,
            "data": {
                "actionType": "AGENT_TALK",
                "speakerId": "agent-1",
                "speakerType": "agent",
                "messageId": "chat-1",
                "content": "A test message",
                "roomId": "room-1",
            },
            "village_id": "village-1",
            "created_at": "2026-05-11 08:00:00.000010",
            "updated_at": "2026-05-11 08:00:00.000010",
        },
        {
            "id": "event-2",
            "event_index": 11,
            "data": {
                "actionType": "CONSOLIDATE",
                "agentId": "agent-1",
                "computerUseSessionId": "session-1",
                "nextSessionGoal": "Continue testing",
                "roomId": "room-1",
            },
            "village_id": "village-1",
            "created_at": "2026-05-11 08:20:00",
            "updated_at": "2026-05-11 08:20:00",
        },
    ]
    write_gzip_rows(raw_dir / "agents.jsonl.gz", [agent])
    write_gzip_rows(raw_dir / "village_goals.jsonl.gz", [village_goal()])
    write_gzip_rows(raw_dir / "agent_goals.jsonl.gz", [agent_goal])
    write_gzip_rows(raw_dir / "chat_messages.jsonl.gz", [chat])
    write_gzip_rows(raw_dir / "computer_use_sessions.jsonl.gz", [session])
    write_gzip_rows(raw_dir / "events.jsonl.gz", events)

    resolved = resolve_episode(raw_dir, goal="Perform novel research!")
    rows, audit = collect_episode(raw_dir, resolved)
    assert len(rows) == 4
    assert audit["missing_chat_links_episode"] == []
    assert audit["missing_session_links_episode"] == []
    chat_row = next(row for row in rows if row["event_kind"] == "chat_message")
    talk_event = next(row for row in rows if row["action_type"] == "AGENT_TALK")
    assert chat_row["linked_high_level_event_id"] == "event-1"
    assert talk_event["linked_chat_message_id"] == "chat-1"
    assert talk_event["agent_name"] == "Test Agent"
    assert talk_event["agent_goal_id"] == "agent-goal-1"

    result = build_episode(
        raw_dir=raw_dir,
        processed_root=tmp_path / "processed",
        output_root=tmp_path / "outputs",
        goal_id="goal-1",
    )
    assert result.row_count == 4
    assert result.parquet_path.is_file()
    assert result.report_path.is_file()
    assert "Total canonical rows: **4**" in result.report_path.read_text(encoding="utf-8")
