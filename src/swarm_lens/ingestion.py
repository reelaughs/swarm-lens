"""Generic, restartable ingestion for one AI Village goal episode."""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import unicodedata
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Mapping

import pyarrow as pa
import pyarrow.parquet as pq

UTC = timezone.utc

SOURCE_FILES = {
    "agents": "agents.jsonl.gz",
    "village_goals": "village_goals.jsonl.gz",
    "agent_goals": "agent_goals.jsonl.gz",
    "chat_messages": "chat_messages.jsonl.gz",
    "computer_use_sessions": "computer_use_sessions.jsonl.gz",
    "events": "events.jsonl.gz",
}

REQUIRED_FIELDS = {
    "agents": {"id", "name", "model_string", "village_id", "created_at", "updated_at"},
    "village_goals": {"id", "village_id", "goal", "start_time", "end_time", "created_at", "updated_at"},
    "agent_goals": {"id", "agent_id", "name", "short_name", "description", "start_time", "end_time", "created_at", "updated_at"},
    "chat_messages": {"id", "agent_speaker_id", "user_speaker_id", "speaker_type", "content", "room_id", "created_at", "updated_at", "has_been_approved"},
    "computer_use_sessions": {"id", "agent_id", "village_id", "session_goal", "short_displayed_session_goal", "created_at", "updated_at", "has_been_asked_to_stop"},
    "events": {"id", "event_index", "data", "village_id", "created_at", "updated_at"},
}


class IngestionError(RuntimeError):
    """Raised when the raw export violates an explicit ingestion assumption."""


@dataclass(frozen=True)
class RawRow:
    table: str
    file: Path
    row_number: int
    record: dict[str, Any]
    sha256: str


@dataclass(frozen=True)
class Episode:
    id: str
    village_id: str
    goal: str
    start: datetime
    end: datetime | None
    slug: str

    def contains(self, timestamp: datetime) -> bool:
        return timestamp >= self.start and (self.end is None or timestamp < self.end)


@dataclass(frozen=True)
class BuildResult:
    episode: Episode
    parquet_path: Path
    report_path: Path
    row_count: int


CANONICAL_SCHEMA = pa.schema(
    [
        pa.field("canonical_event_id", pa.string(), nullable=False),
        pa.field("event_kind", pa.string(), nullable=False),
        pa.field("event_timestamp", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("event_index", pa.int64()),
        pa.field("action_type", pa.string()),
        pa.field("agent_id", pa.string()),
        pa.field("agent_name", pa.string()),
        pa.field("agent_model", pa.string()),
        pa.field("user_id", pa.string()),
        pa.field("speaker_type", pa.string()),
        pa.field("speaker_name", pa.string()),
        pa.field("chat_content", pa.string()),
        pa.field("session_goal", pa.string()),
        pa.field("short_displayed_session_goal", pa.string()),
        pa.field("event_content", pa.string()),
        pa.field("event_summary", pa.string()),
        pa.field("search_query", pa.string()),
        pa.field("search_answer", pa.string()),
        pa.field("next_session_goal", pa.string()),
        pa.field("next_short_displayed_session_goal", pa.string()),
        pa.field("pause_seconds", pa.int64()),
        pa.field("room_id", pa.string()),
        pa.field("computer_use_session_id", pa.string()),
        pa.field("village_id", pa.string(), nullable=False),
        pa.field("village_goal_id", pa.string(), nullable=False),
        pa.field("village_goal_text", pa.string(), nullable=False),
        pa.field("village_goal_start", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("village_goal_end", pa.timestamp("us", tz="UTC")),
        pa.field("agent_goal_id", pa.string()),
        pa.field("agent_goal_name", pa.string()),
        pa.field("agent_goal_short_name", pa.string()),
        pa.field("agent_goal_description", pa.string()),
        pa.field("agent_goal_start", pa.timestamp("us", tz="UTC")),
        pa.field("agent_goal_end", pa.timestamp("us", tz="UTC")),
        pa.field("linked_chat_message_id", pa.string()),
        pa.field("linked_high_level_event_id", pa.string()),
        pa.field("linked_high_level_event_index", pa.int64()),
        pa.field("source_table", pa.string(), nullable=False),
        pa.field("source_file", pa.string(), nullable=False),
        pa.field("source_row_number", pa.int64(), nullable=False),
        pa.field("source_row_id", pa.string(), nullable=False),
        pa.field("source_created_at", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("source_updated_at", pa.timestamp("us", tz="UTC")),
        pa.field("source_record_sha256", pa.string(), nullable=False),
    ]
)


def parse_timestamp(value: Any, *, field: str, allow_none: bool = False) -> datetime | None:
    """Parse the export's naive UTC timestamps without accepting silent coercions."""
    if value is None:
        if allow_none:
            return None
        raise IngestionError(f"{field} must not be null")
    if not isinstance(value, str) or not value:
        raise IngestionError(f"{field} must be a non-empty timestamp string; got {value!r}")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise IngestionError(f"invalid timestamp in {field}: {value!r}") from exc
    if parsed.tzinfo is not None:
        raise IngestionError(f"{field} unexpectedly contains timezone information: {value!r}")
    return parsed.replace(tzinfo=UTC)


def safe_slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    return slug or "episode"


def _validate_record(table: str, record: Any, row_number: int) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise IngestionError(f"{table} row {row_number} is not a JSON object")
    missing = REQUIRED_FIELDS[table] - record.keys()
    if missing:
        raise IngestionError(f"{table} row {row_number} is missing fields: {sorted(missing)}")
    if not isinstance(record.get("id"), str) or not record["id"]:
        raise IngestionError(f"{table} row {row_number} has invalid id: {record.get('id')!r}")
    return record


def iter_raw_rows(raw_dir: Path, table: str) -> Iterator[RawRow]:
    path = raw_dir / SOURCE_FILES[table]
    if not path.is_file():
        raise IngestionError(f"missing raw source: {path}")
    with gzip.open(path, "rb") as stream:
        for row_number, raw_line_with_ending in enumerate(stream, start=1):
            raw_line = raw_line_with_ending.rstrip(b"\r\n")
            if not raw_line:
                raise IngestionError(f"{table} row {row_number} is blank")
            try:
                record = json.loads(raw_line)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise IngestionError(f"{table} row {row_number} is invalid JSON") from exc
            yield RawRow(
                table=table,
                file=path,
                row_number=row_number,
                record=_validate_record(table, record, row_number),
                sha256=hashlib.sha256(raw_line).hexdigest(),
            )


def _read_small_table(raw_dir: Path, table: str) -> list[RawRow]:
    return list(iter_raw_rows(raw_dir, table))


def resolve_episode(
    raw_dir: Path,
    *,
    goal: str | None = None,
    goal_id: str | None = None,
) -> Episode:
    """Resolve one authoritative episode by exact goal text or UUID."""
    if (goal is None) == (goal_id is None):
        raise IngestionError("provide exactly one of goal or goal_id")
    goal_rows = _read_small_table(Path(raw_dir), "village_goals")
    matches = [row for row in goal_rows if row.record["goal"] == goal] if goal is not None else [row for row in goal_rows if row.record["id"] == goal_id]
    selector = f"goal={goal!r}" if goal is not None else f"goal_id={goal_id!r}"
    if len(matches) != 1:
        raise IngestionError(f"expected exactly one village goal for {selector}; found {len(matches)}")
    record = matches[0].record
    start = parse_timestamp(record["start_time"], field="village_goals.start_time")
    end = parse_timestamp(record["end_time"], field="village_goals.end_time", allow_none=True)
    assert start is not None
    if end is not None and end <= start:
        raise IngestionError(f"goal {record['id']} has non-positive interval")

    base_slug = safe_slug(record["goal"])
    colliding_ids = {
        row.record["id"] for row in goal_rows if safe_slug(row.record["goal"]) == base_slug
    }
    slug = base_slug if len(colliding_ids) == 1 else f"{base_slug}-{record['id'][:8]}"
    return Episode(
        id=record["id"],
        village_id=record["village_id"],
        goal=record["goal"],
        start=start,
        end=end,
        slug=slug,
    )


def _require_unique(rows: Iterable[RawRow], table: str) -> dict[str, RawRow]:
    result: dict[str, RawRow] = {}
    for row in rows:
        row_id = row.record["id"]
        if row_id in result:
            raise IngestionError(f"duplicate {table}.id: {row_id}")
        result[row_id] = row
    return result


def _active_agent_goal(
    goals_by_agent: Mapping[str, list[tuple[RawRow, datetime | None, datetime | None]]],
    agent_id: str | None,
    timestamp: datetime,
) -> tuple[RawRow, datetime | None, datetime | None] | None:
    if agent_id is None:
        return None
    active = [
        goal
        for goal in goals_by_agent.get(agent_id, [])
        if (goal[1] is None or goal[1] <= timestamp) and (goal[2] is None or timestamp < goal[2])
    ]
    if len(active) > 1:
        ids = [item[0].record["id"] for item in active]
        raise IngestionError(f"agent {agent_id} has overlapping active goals at {timestamp.isoformat()}: {ids}")
    return active[0] if active else None


def _chat_link_id(data: Mapping[str, Any], event_id: str) -> str | None:
    values = {data.get("messageId"), data.get("chatMessageId")} - {None, ""}
    if len(values) > 1:
        raise IngestionError(f"event {event_id} has conflicting messageId/chatMessageId: {sorted(values)}")
    value = next(iter(values), None)
    if value is not None and not isinstance(value, str):
        raise IngestionError(f"event {event_id} has non-string chat message ID")
    return value


def _base_canonical_row(
    raw: RawRow,
    episode: Episode,
    event_kind: str,
    timestamp: datetime,
    agent_id: str | None,
    agents: Mapping[str, RawRow],
    goals_by_agent: Mapping[str, list[tuple[RawRow, datetime | None, datetime | None]]],
) -> dict[str, Any]:
    agent = agents.get(agent_id) if agent_id else None
    active_goal = _active_agent_goal(goals_by_agent, agent_id, timestamp)
    agent_goal_row = active_goal[0].record if active_goal else None
    return {
        "canonical_event_id": f"{raw.table}:{raw.record['id']}",
        "event_kind": event_kind,
        "event_timestamp": timestamp,
        "event_index": None,
        "action_type": None,
        "agent_id": agent_id,
        "agent_name": agent.record["name"] if agent else None,
        "agent_model": agent.record["model_string"] if agent else None,
        "user_id": None,
        "speaker_type": None,
        "speaker_name": agent.record["name"] if agent else None,
        "chat_content": None,
        "session_goal": None,
        "short_displayed_session_goal": None,
        "event_content": None,
        "event_summary": None,
        "search_query": None,
        "search_answer": None,
        "next_session_goal": None,
        "next_short_displayed_session_goal": None,
        "pause_seconds": None,
        "room_id": None,
        "computer_use_session_id": None,
        "village_id": episode.village_id,
        "village_goal_id": episode.id,
        "village_goal_text": episode.goal,
        "village_goal_start": episode.start,
        "village_goal_end": episode.end,
        "agent_goal_id": agent_goal_row["id"] if agent_goal_row else None,
        "agent_goal_name": agent_goal_row["name"] if agent_goal_row else None,
        "agent_goal_short_name": agent_goal_row["short_name"] if agent_goal_row else None,
        "agent_goal_description": agent_goal_row["description"] if agent_goal_row else None,
        "agent_goal_start": active_goal[1] if active_goal else None,
        "agent_goal_end": active_goal[2] if active_goal else None,
        "linked_chat_message_id": None,
        "linked_high_level_event_id": None,
        "linked_high_level_event_index": None,
        "source_table": raw.table,
        "source_file": raw.file.name,
        "source_row_number": raw.row_number,
        "source_row_id": raw.record["id"],
        "source_created_at": timestamp,
        "source_updated_at": parse_timestamp(raw.record.get("updated_at"), field=f"{raw.table}.updated_at", allow_none=True),
        "source_record_sha256": raw.sha256,
    }


def _validate_agent_reference(agent_id: str | None, agents: Mapping[str, RawRow], context: str) -> None:
    if agent_id is not None and agent_id not in agents:
        raise IngestionError(f"{context} references missing agent {agent_id}")


def _assert_string_or_none(value: Any, context: str) -> str | None:
    if value is not None and not isinstance(value, str):
        raise IngestionError(f"{context} must be a string or null; got {value!r}")
    return value


def _assert_int_or_none(value: Any, context: str) -> int | None:
    if value is not None and (not isinstance(value, int) or isinstance(value, bool)):
        raise IngestionError(f"{context} must be an integer or null; got {value!r}")
    return value


def collect_episode(
    raw_dir: Path,
    episode: Episode,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Stream the export once per large table and return canonical rows plus audit facts."""
    raw_dir = Path(raw_dir)
    agent_rows = _read_small_table(raw_dir, "agents")
    village_goal_rows = _read_small_table(raw_dir, "village_goals")
    agent_goal_rows = _read_small_table(raw_dir, "agent_goals")
    agents = _require_unique(agent_rows, "agents")
    _require_unique(village_goal_rows, "village_goals")
    _require_unique(agent_goal_rows, "agent_goals")

    for row in agents.values():
        if row.record["village_id"] != episode.village_id:
            raise IngestionError(f"agent {row.record['id']} belongs to unexpected village {row.record['village_id']}")

    goals_by_agent: dict[str, list[tuple[RawRow, datetime | None, datetime | None]]] = defaultdict(list)
    for row in agent_goal_rows:
        agent_id = row.record["agent_id"]
        _validate_agent_reference(agent_id, agents, f"agent_goals row {row.row_number}")
        start = parse_timestamp(row.record["start_time"], field="agent_goals.start_time", allow_none=True)
        end = parse_timestamp(row.record["end_time"], field="agent_goals.end_time", allow_none=True)
        if start is not None and end is not None and end <= start:
            raise IngestionError(f"agent goal {row.record['id']} has non-positive interval")
        goals_by_agent[agent_id].append((row, start, end))

    counts_before = {
        "agents": len(agent_rows),
        "village_goals": len(village_goal_rows),
        "agent_goals": len(agent_goal_rows),
        "events": 0,
        "chat_messages": 0,
        "computer_use_sessions": 0,
    }
    extra_fields: dict[str, set[str]] = defaultdict(set)
    rows: list[dict[str, Any]] = []
    seen_source_ids: dict[str, set[str]] = defaultdict(set)
    seen_event_indexes: set[int] = set()
    event_timestamps_by_index: list[tuple[int, datetime]] = []
    event_by_chat_id: dict[str, tuple[str, int, dict[str, Any], datetime, bool]] = {}
    required_chat_links: set[str] = set()
    required_chat_links_episode: set[str] = set()
    required_session_links: set[str] = set()
    required_session_links_episode: set[str] = set()

    for raw in iter_raw_rows(raw_dir, "events"):
        counts_before["events"] += 1
        record = raw.record
        if record["id"] in seen_source_ids["events"]:
            raise IngestionError(f"duplicate events.id: {record['id']}")
        seen_source_ids["events"].add(record["id"])
        extra_fields["events"].update(record.keys() - REQUIRED_FIELDS["events"])
        index = _assert_int_or_none(record["event_index"], f"events row {raw.row_number} event_index")
        if index is None:
            raise IngestionError(f"events row {raw.row_number} has null event_index")
        if index in seen_event_indexes:
            raise IngestionError(f"duplicate events.event_index: {index}")
        seen_event_indexes.add(index)
        timestamp = parse_timestamp(record["created_at"], field="events.created_at")
        assert timestamp is not None
        event_timestamps_by_index.append((index, timestamp))
        data = record["data"]
        if not isinstance(data, dict) or not isinstance(data.get("actionType"), str):
            raise IngestionError(f"events row {raw.row_number} has invalid data/actionType")
        action_type = data["actionType"]
        agent_id = data.get("speakerId") if action_type == "AGENT_TALK" else data.get("agentId")
        agent_id = _assert_string_or_none(agent_id, f"events row {raw.row_number} agent ID")
        _validate_agent_reference(agent_id, agents, f"event {record['id']}")
        chat_id = _chat_link_id(data, record["id"])
        session_id = _assert_string_or_none(data.get("computerUseSessionId"), f"event {record['id']} computerUseSessionId")
        event_in_episode = episode.contains(timestamp) and record["village_id"] == episode.village_id
        if chat_id:
            if chat_id in event_by_chat_id:
                raise IngestionError(f"multiple events link to chat message {chat_id}")
            event_by_chat_id[chat_id] = (record["id"], index, data, timestamp, event_in_episode)
            required_chat_links.add(chat_id)
            if event_in_episode:
                required_chat_links_episode.add(chat_id)
        if session_id:
            required_session_links.add(session_id)
            if event_in_episode:
                required_session_links_episode.add(session_id)

        if not event_in_episode:
            continue
        canonical = _base_canonical_row(raw, episode, "high_level_event", timestamp, agent_id, agents, goals_by_agent)
        canonical.update(
            event_index=index,
            action_type=action_type,
            user_id=_assert_string_or_none(data.get("speakerId"), f"event {record['id']} user ID") if action_type == "USER_TALK" else None,
            speaker_type=_assert_string_or_none(data.get("speakerType"), f"event {record['id']} speakerType"),
            speaker_name=_assert_string_or_none(data.get("speakerName"), f"event {record['id']} speakerName") or canonical["speaker_name"],
            event_content=_assert_string_or_none(data.get("content"), f"event {record['id']} content"),
            event_summary=_assert_string_or_none(data.get("summary"), f"event {record['id']} summary"),
            search_query=_assert_string_or_none(data.get("query"), f"event {record['id']} query"),
            search_answer=_assert_string_or_none(data.get("answerToQuery"), f"event {record['id']} answerToQuery"),
            next_session_goal=_assert_string_or_none(data.get("nextSessionGoal"), f"event {record['id']} nextSessionGoal"),
            next_short_displayed_session_goal=_assert_string_or_none(data.get("nextShortDisplayedSessionGoal"), f"event {record['id']} nextShortDisplayedSessionGoal"),
            pause_seconds=_assert_int_or_none(data.get("seconds"), f"event {record['id']} seconds"),
            room_id=_assert_string_or_none(data.get("roomId"), f"event {record['id']} roomId"),
            computer_use_session_id=session_id,
            linked_chat_message_id=chat_id,
        )
        rows.append(canonical)

    chat_link_rows: dict[str, RawRow] = {}
    for raw in iter_raw_rows(raw_dir, "chat_messages"):
        counts_before["chat_messages"] += 1
        record = raw.record
        if record["id"] in seen_source_ids["chat_messages"]:
            raise IngestionError(f"duplicate chat_messages.id: {record['id']}")
        seen_source_ids["chat_messages"].add(record["id"])
        extra_fields["chat_messages"].update(record.keys() - REQUIRED_FIELDS["chat_messages"])
        timestamp = parse_timestamp(record["created_at"], field="chat_messages.created_at")
        assert timestamp is not None
        if record["id"] in required_chat_links:
            chat_link_rows[record["id"]] = raw
        if not episode.contains(timestamp):
            continue
        speaker_type = record["speaker_type"]
        if speaker_type not in {"agent", "user"}:
            raise IngestionError(f"chat message {record['id']} has unknown speaker_type {speaker_type!r}")
        agent_id = record["agent_speaker_id"] if speaker_type == "agent" else None
        user_id = record["user_speaker_id"] if speaker_type == "user" else None
        _validate_agent_reference(agent_id, agents, f"chat message {record['id']}")
        linked = event_by_chat_id.get(record["id"])
        canonical = _base_canonical_row(raw, episode, "chat_message", timestamp, agent_id, agents, goals_by_agent)
        canonical.update(
            user_id=user_id,
            speaker_type=speaker_type,
            speaker_name=(linked[2].get("speakerName") if linked and speaker_type == "user" else canonical["speaker_name"]),
            chat_content=record["content"],
            room_id=record["room_id"],
            linked_high_level_event_id=linked[0] if linked else None,
            linked_high_level_event_index=linked[1] if linked else None,
        )
        rows.append(canonical)

    session_link_rows: dict[str, RawRow] = {}
    for raw in iter_raw_rows(raw_dir, "computer_use_sessions"):
        counts_before["computer_use_sessions"] += 1
        record = raw.record
        if record["id"] in seen_source_ids["computer_use_sessions"]:
            raise IngestionError(f"duplicate computer_use_sessions.id: {record['id']}")
        seen_source_ids["computer_use_sessions"].add(record["id"])
        extra_fields["computer_use_sessions"].update(record.keys() - REQUIRED_FIELDS["computer_use_sessions"])
        timestamp = parse_timestamp(record["created_at"], field="computer_use_sessions.created_at")
        assert timestamp is not None
        if record["id"] in required_session_links:
            session_link_rows[record["id"]] = raw
        if not episode.contains(timestamp) or record["village_id"] != episode.village_id:
            continue
        agent_id = record["agent_id"]
        _validate_agent_reference(agent_id, agents, f"computer use session {record['id']}")
        canonical = _base_canonical_row(raw, episode, "computer_use_session_goal", timestamp, agent_id, agents, goals_by_agent)
        canonical.update(
            session_goal=record["session_goal"],
            short_displayed_session_goal=record["short_displayed_session_goal"],
            computer_use_session_id=record["id"],
        )
        rows.append(canonical)

    missing_chat_links = sorted(required_chat_links - chat_link_rows.keys())
    missing_chat_links_episode = sorted(required_chat_links_episode - chat_link_rows.keys())
    missing_session_links = sorted(required_session_links - session_link_rows.keys())
    missing_session_links_episode = sorted(required_session_links_episode - session_link_rows.keys())

    chat_mismatch_counts: Counter[str] = Counter()
    chat_mismatch_counts_episode: Counter[str] = Counter()
    chat_mismatch_examples: list[str] = []
    chat_mismatch_examples_episode: list[str] = []
    timestamp_deltas_us: list[int] = []
    timestamp_deltas_us_episode: list[int] = []
    for chat_id, chat_raw in chat_link_rows.items():
        _, _, event_data, event_time, event_in_episode = event_by_chat_id[chat_id]
        chat = chat_raw.record
        comparisons = {
            "content": (event_data.get("content"), chat.get("content")),
            "room_id": (event_data.get("roomId"), chat.get("room_id")),
        }
        if event_data.get("actionType") == "AGENT_TALK":
            comparisons["agent_id"] = (event_data.get("speakerId"), chat.get("agent_speaker_id"))
        for label, pair in comparisons.items():
            if pair[0] is not None and pair[0] != pair[1]:
                chat_mismatch_counts[label] += 1
                if len(chat_mismatch_examples) < 10:
                    chat_mismatch_examples.append(f"{chat_id}:{label}")
                if event_in_episode:
                    chat_mismatch_counts_episode[label] += 1
                    if len(chat_mismatch_examples_episode) < 10:
                        chat_mismatch_examples_episode.append(f"{chat_id}:{label}")
        chat_time = parse_timestamp(chat["created_at"], field="chat_messages.created_at")
        assert chat_time is not None
        delta_us = int((event_time - chat_time).total_seconds() * 1_000_000)
        timestamp_deltas_us.append(delta_us)
        if event_in_episode:
            timestamp_deltas_us_episode.append(delta_us)

    canonical_ids = [row["canonical_event_id"] for row in rows]
    if len(canonical_ids) != len(set(canonical_ids)):
        raise IngestionError("canonical_event_id is not unique")

    sorted_event_times = [timestamp for _, timestamp in sorted(event_timestamps_by_index)]
    ordering_inversions = sum(
        current < previous for previous, current in zip(sorted_event_times, sorted_event_times[1:])
    )
    rows.sort(
        key=lambda row: (
            row["event_timestamp"],
            row["event_index"] if row["event_index"] is not None else row["linked_high_level_event_index"] if row["linked_high_level_event_index"] is not None else 2**63 - 1,
            row["event_kind"],
            row["canonical_event_id"],
        )
    )
    audit = {
        "counts_before": counts_before,
        "extra_fields": {table: sorted(fields) for table, fields in extra_fields.items()},
        "missing_chat_links": missing_chat_links,
        "missing_chat_links_episode": missing_chat_links_episode,
        "missing_session_links": missing_session_links,
        "missing_session_links_episode": missing_session_links_episode,
        "chat_mismatch_counts": dict(chat_mismatch_counts),
        "chat_mismatch_counts_episode": dict(chat_mismatch_counts_episode),
        "chat_mismatch_examples": chat_mismatch_examples,
        "chat_mismatch_examples_episode": chat_mismatch_examples_episode,
        "chat_timestamp_delta_us": {
            "count": len(timestamp_deltas_us),
            "min": min(timestamp_deltas_us, default=None),
            "max": max(timestamp_deltas_us, default=None),
        },
        "chat_timestamp_delta_us_episode": {
            "count": len(timestamp_deltas_us_episode),
            "min": min(timestamp_deltas_us_episode, default=None),
            "max": max(timestamp_deltas_us_episode, default=None),
        },
        "ordering_inversions": ordering_inversions,
    }
    return rows, audit


def _atomic_write_parquet(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        table = pa.Table.from_pylist(rows, schema=CANONICAL_SCHEMA)
        pq.write_table(table, temp_path, compression="zstd")
        check = pq.read_table(temp_path)
        if check.schema != CANONICAL_SCHEMA or check.num_rows != len(rows):
            raise IngestionError("Parquet round-trip validation failed")
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def _atomic_write_text(content: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temp_path.write_text(content, encoding="utf-8", newline="\n")
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def build_episode(
    *,
    raw_dir: Path,
    processed_root: Path,
    output_root: Path,
    goal: str | None = None,
    goal_id: str | None = None,
) -> BuildResult:
    """Build and validate one episode without embedding any episode-specific logic."""
    from .validation import render_validation_report, validate_canonical_rows

    raw_dir = Path(raw_dir)
    episode = resolve_episode(raw_dir, goal=goal, goal_id=goal_id)
    rows, audit = collect_episode(raw_dir, episode)
    validation = validate_canonical_rows(rows, episode, audit)
    parquet_path = Path(processed_root) / episode.slug / "events.parquet"
    report_path = Path(output_root) / episode.slug / "ingestion_validation.md"
    _atomic_write_parquet(rows, parquet_path)
    report = render_validation_report(rows, episode, audit, validation, parquet_path)
    _atomic_write_text(report, report_path)
    return BuildResult(episode, parquet_path, report_path, len(rows))
