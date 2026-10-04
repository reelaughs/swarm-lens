"""Logical evidence items with linked chat/event pairs counted once."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Sequence

from swarm_lens.turning_points.brief import EvidenceCollector


def _record_view(row: Mapping[str, Any], boundary: datetime) -> dict[str, Any]:
    action_type = row.get("action_type")
    chat_text = row.get("chat_content")
    if chat_text is None and action_type in {"AGENT_TALK", "USER_TALK"}:
        chat_text = row.get("event_content")
    return {
        "relation": "before" if row["event_timestamp"] < boundary else "after",
        "timestamp": row["event_timestamp"],
        "canonical_event_id": row["canonical_event_id"],
        "source_table": row["source_table"],
        "source_row_id": row["source_row_id"],
        "event_index": row.get("event_index") if row.get("event_index") is not None else row.get("linked_high_level_event_index"),
        "linked_high_level_event_id": row.get("linked_high_level_event_id"),
        "linked_high_level_event_index": row.get("linked_high_level_event_index"),
        "agent_id": row.get("agent_id"),
        "agent_name": row.get("agent_name") or row.get("speaker_name"),
        "agent_model": row.get("agent_model"),
        "speaker_type": row.get("speaker_type"),
        "event_kind": row["event_kind"],
        "action_type": action_type,
        "chat_text": chat_text,
        "session_goal": row.get("session_goal"),
        "event_content": row.get("event_content"),
        "event_summary": row.get("event_summary"),
        "search_query": row.get("search_query"),
        "search_answer": row.get("search_answer"),
        "room_id": row.get("room_id"),
        "computer_use_session_id": row.get("computer_use_session_id"),
    }


def source_family(item: Mapping[str, Any]) -> str:
    """Return the source family used for directed similarity thresholds."""
    if item["source_type"] in {"chat", "user_talk"}:
        return "chat"
    if item["source_type"] == "session_goal":
        return "session_goal"
    return str(item["source_type"])


def build_logical_items(
    canonical_rows: Sequence[Mapping[str, Any]],
    *,
    boundary: datetime,
    start: datetime,
    end: datetime,
    baseline_start: datetime,
    antecedent_start: datetime,
) -> list[dict[str, Any]]:
    selected = [row for row in canonical_rows if start <= row["event_timestamp"] < end]
    views = [_record_view(row, boundary) for row in selected]
    collector = EvidenceCollector(views)
    for view in views:
        collector.add_record(view, category="stage3_source", reason="included in reconstruction interval")
    by_canonical = {view["canonical_event_id"]: view for view in views}
    items: list[dict[str, Any]] = []
    for collected in collector.items.values():
        primary = by_canonical[collected["provenance"][0]["canonical_event_id"]]
        timestamp = collected["timestamp"]
        phase = "baseline" if timestamp < antecedent_start else "antecedent" if timestamp < boundary else "followup"
        if timestamp < baseline_start:
            continue
        if collected["event_kind"] == "logical_chat":
            source_type = "user_talk" if collected.get("action_type") == "USER_TALK" or primary.get("speaker_type") == "user" else "chat"
        elif collected["event_kind"] == "computer_use_session_goal":
            source_type = "session_goal"
        else:
            source_type = "high_level_action"
        text = collected.get("text")
        if not text:
            text = primary.get("event_content") or primary.get("event_summary") or primary.get("search_query") or primary.get("search_answer")
        items.append(
            {
                "logical_item_id": collected["display_key"],
                "timestamp": timestamp,
                "phase": phase,
                "relation": collected["relation"],
                "agent_id": primary.get("agent_id"),
                "agent_name": collected.get("agent_name"),
                "agent_model": collected.get("agent_model"),
                "speaker_type": primary.get("speaker_type"),
                "source_type": source_type,
                "event_kind": collected["event_kind"],
                "action_type": collected.get("action_type"),
                "room_id": collected.get("room_id"),
                "computer_use_session_id": primary.get("computer_use_session_id"),
                "text": text,
                "provenance": collected["provenance"],
            }
        )
    items.sort(key=lambda row: (row["timestamp"], row["logical_item_id"]))
    return items

