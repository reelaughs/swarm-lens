from __future__ import annotations

from datetime import datetime, timezone

import pytest

from swarm_lens.turning_points.brief import EvidenceCollector
from swarm_lens.turning_points.context import _external_context, parse_dated_changelog_sections, parse_roster_table, select_context_records

UTC = timezone.utc


def test_context_selection_is_half_open_and_sorted() -> None:
    boundary = datetime(2026, 5, 20, 12, 0, tzinfo=UTC)
    rows = [
        {"canonical_event_id": "end", "event_timestamp": datetime(2026, 5, 20, 13, 30, tzinfo=UTC)},
        {"canonical_event_id": "after", "event_timestamp": datetime(2026, 5, 20, 12, 1, tzinfo=UTC)},
        {"canonical_event_id": "start", "event_timestamp": datetime(2026, 5, 20, 10, 30, tzinfo=UTC)},
        {"canonical_event_id": "before", "event_timestamp": datetime(2026, 5, 20, 11, 59, tzinfo=UTC)},
    ]
    for row in rows:
        row.update(event_index=None, linked_high_level_event_index=None)
    start, end, selected = select_context_records(rows, boundary, before_minutes=90, after_minutes=90)
    assert start == datetime(2026, 5, 20, 10, 30, tzinfo=UTC)
    assert end == datetime(2026, 5, 20, 13, 30, tzinfo=UTC)
    assert [row["canonical_event_id"] for row in selected] == ["start", "before", "after"]


def test_dated_changelog_sections_support_ranges() -> None:
    text = """## 2026-05-21

- One change.

## 2026-05-22 to 2026-05-23 — range

- Another change.
"""
    sections = parse_dated_changelog_sections(text)
    assert len(sections) == 2
    assert sections[0].start_date.isoformat() == "2026-05-21"
    assert sections[1].end_date.isoformat() == "2026-05-23"
    assert "Another change" in sections[1].body


def test_roster_parser_extracts_date_level_joins_and_departures() -> None:
    text = """## Agent roster

| Agent | Model string | Joined | Left |
| --- | --- | --- | --- |
| Test Agent | `model-x` | 2026-05-20 | 2026-05-22 |
| Active Agent | `model-y` | 2026-05-21 | active |

---
"""
    rows = parse_roster_table(text)
    assert rows == [
        {"agent_name": "Test Agent", "model": "model-x", "joined": "2026-05-20", "left": "2026-05-22"},
        {"agent_name": "Active Agent", "model": "model-y", "joined": "2026-05-21", "left": None},
    ]


def test_raw_agent_created_at_is_primary_join_source_even_outside_packet_same_day() -> None:
    boundary = datetime(2026, 5, 20, 20, 0, tzinfo=UTC)
    changelog = """## Agent roster

| Agent | Model string | Joined | Left |
| --- | --- | --- | --- |
| Gemini Test | `gemini-test` | 2026-05-20 | active |

---
"""
    external = _external_context(
        [],
        boundary=boundary,
        start=datetime(2026, 5, 20, 18, 30, tzinfo=UTC),
        end=datetime(2026, 5, 20, 21, 30, tzinfo=UTC),
        changelog_text=changelog,
        agents=[
            {
                "id": "agent-1",
                "name": "Gemini Test",
                "model_string": "gemini-test",
                "created_at": "2026-05-20 16:26:28.037637",
            }
        ],
        village_goals=[],
    )
    assert len(external["agent_roster_changes"]) == 1
    change = external["agent_roster_changes"][0]
    assert change["source"] == "agents.jsonl.gz created_at"
    assert change["precision"] == "timestamp"
    assert change["within_context_interval"] is False
    assert change["minutes_from_boundary"] == pytest.approx(-213.53270605)


def test_linked_chat_and_event_collapse_to_one_display_item() -> None:
    chat = {
        "canonical_event_id": "chat_messages:chat-1",
        "source_table": "chat_messages",
        "source_row_id": "chat-1",
        "event_index": 10,
        "linked_high_level_event_id": "event-1",
        "event_kind": "chat_message",
        "action_type": None,
        "timestamp": "2026-05-20T20:00:00+00:00",
        "relation": "after",
        "agent_name": "Agent",
        "agent_model": "model",
        "room_id": "room",
        "chat_text": "hello",
        "session_goal": None,
    }
    event = {
        **chat,
        "canonical_event_id": "events:event-1",
        "source_table": "events",
        "source_row_id": "event-1",
        "event_kind": "high_level_event",
        "action_type": "AGENT_TALK",
        "linked_high_level_event_id": None,
    }
    collector = EvidenceCollector([chat, event])
    collector.add_record(chat, category="communication_representative", reason="test")
    collector.add_record(event, category="participation_representative", reason="test event")
    assert len(collector.items) == 1
    item = next(iter(collector.items.values()))
    assert item["event_kind"] == "logical_chat"
    assert len(item["provenance"]) == 2
    assert item["categories"] == ["communication_representative", "participation_representative"]
