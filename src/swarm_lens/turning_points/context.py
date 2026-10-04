"""Deterministic evidence packets for manual turning-point adjudication."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Mapping, Sequence

import pyarrow.parquet as pq

from swarm_lens.ingestion import iter_raw_rows, parse_timestamp

DATE_HEADING = re.compile(r"^## (\d{4}-\d{2}-\d{2})(?: to (\d{4}-\d{2}-\d{2}))?(?:\s+—.*)?$")


@dataclass(frozen=True)
class DatedSection:
    start_date: date
    end_date: date
    heading: str
    body: str


def select_context_records(
    rows: Sequence[Mapping[str, Any]],
    boundary: datetime,
    *,
    before_minutes: int,
    after_minutes: int,
) -> tuple[datetime, datetime, list[dict[str, Any]]]:
    start = boundary - timedelta(minutes=before_minutes)
    end = boundary + timedelta(minutes=after_minutes)
    selected = [dict(row) for row in rows if start <= row["event_timestamp"] < end]
    selected.sort(
        key=lambda row: (
            row["event_timestamp"],
            row.get("event_index") if row.get("event_index") is not None else row.get("linked_high_level_event_index") if row.get("linked_high_level_event_index") is not None else 2**63 - 1,
            row["canonical_event_id"],
        )
    )
    return start, end, selected


def parse_dated_changelog_sections(text: str) -> list[DatedSection]:
    lines = text.splitlines()
    sections: list[DatedSection] = []
    index = 0
    while index < len(lines):
        match = DATE_HEADING.match(lines[index])
        if not match:
            index += 1
            continue
        heading = lines[index][3:].strip()
        start = date.fromisoformat(match.group(1))
        end = date.fromisoformat(match.group(2) or match.group(1))
        body_lines: list[str] = []
        index += 1
        while index < len(lines) and not lines[index].startswith("## "):
            if lines[index].strip() and lines[index].strip() != "---":
                body_lines.append(lines[index].strip())
            index += 1
        sections.append(DatedSection(start, end, heading, "\n".join(body_lines)))
    return sections


def parse_roster_table(text: str) -> list[dict[str, str | None]]:
    start_marker = "## Agent roster"
    start = text.find(start_marker)
    if start < 0:
        return []
    rows: list[dict[str, str | None]] = []
    for line in text[start:].splitlines():
        if line.strip() == "---":
            break
        if not line.startswith("|"):
            continue
        cells = [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]
        if len(cells) != 4 or cells[0] in {"Agent", "---"} or set(cells[0]) == {"-"}:
            continue
        joined = cells[2] if re.fullmatch(r"\d{4}-\d{2}-\d{2}", cells[2]) else None
        left = cells[3] if re.fullmatch(r"\d{4}-\d{2}-\d{2}", cells[3]) else None
        rows.append({"agent_name": cells[0], "model": cells[1], "joined": joined, "left": left})
    return rows


def _dates_overlapping(start: datetime, end: datetime) -> set[date]:
    last_included = end - timedelta(microseconds=1)
    dates: set[date] = set()
    current = start.date()
    while current <= last_included.date():
        dates.add(current)
        current += timedelta(days=1)
    return dates


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
        "event_kind": row["event_kind"],
        "action_type": action_type,
        "chat_text": chat_text,
        "session_goal": row.get("session_goal"),
        "room_id": row.get("room_id"),
        "computer_use_session_id": row.get("computer_use_session_id"),
    }


def _external_context(
    selected_rows: Sequence[Mapping[str, Any]],
    *,
    boundary: datetime,
    start: datetime,
    end: datetime,
    changelog_text: str,
    agents: Sequence[Mapping[str, Any]],
    village_goals: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    relevant_dates = _dates_overlapping(start, end)
    user_talk = [
        _record_view(row, boundary)
        for row in selected_rows
        if row["event_kind"] == "high_level_event" and row.get("action_type") == "USER_TALK"
    ]
    raw_joins = []
    raw_join_keys: set[tuple[str, str]] = set()
    for agent in agents:
        joined = parse_timestamp(agent["created_at"], field="agents.created_at")
        if joined is not None and (start <= joined < end or joined.date() in relevant_dates):
            raw_join_keys.add((agent["name"].casefold(), agent["model_string"].casefold()))
            raw_joins.append(
                {
                    "timestamp": joined,
                    "agent_id": agent["id"],
                    "agent_name": agent["name"],
                    "model": agent["model_string"],
                    "change": "join",
                    "source": "agents.jsonl.gz created_at",
                    "precision": "timestamp",
                    "within_context_interval": start <= joined < end,
                    "same_utc_date": joined.date() in relevant_dates,
                    "minutes_from_boundary": (joined - boundary).total_seconds() / 60,
                }
            )
    roster_changes = []
    for roster in parse_roster_table(changelog_text):
        for field, change in (("joined", "join"), ("left", "departure")):
            value = roster[field]
            if value and date.fromisoformat(value) in relevant_dates:
                if change == "join" and (str(roster["agent_name"]).casefold(), str(roster["model"]).casefold()) in raw_join_keys:
                    continue
                roster_changes.append(
                    {
                        "date": value,
                        "agent_name": roster["agent_name"],
                        "model": roster["model"],
                        "change": change,
                        "source": "CHANGELOG.md agent roster",
                        "precision": "date",
                        "within_context_interval": None,
                        "same_utc_date": True,
                        "minutes_from_boundary": None,
                    }
                )
    goal_boundaries = []
    for goal in village_goals:
        for field, boundary_type in (("start_time", "start"), ("end_time", "end")):
            timestamp = parse_timestamp(goal[field], field=f"village_goals.{field}", allow_none=True)
            if timestamp is not None and start <= timestamp < end:
                goal_boundaries.append(
                    {
                        "timestamp": timestamp,
                        "boundary": boundary_type,
                        "village_goal_id": goal["id"],
                        "village_goal_text": goal["goal"],
                        "source": "village_goals.jsonl.gz",
                    }
                )
    scaffolding = [
        {
            "start_date": section.start_date.isoformat(),
            "end_date": section.end_date.isoformat(),
            "heading": section.heading,
            "details": section.body,
            "source": "CHANGELOG.md",
            "precision": "date",
        }
        for section in parse_dated_changelog_sections(changelog_text)
        if any(section.start_date <= day <= section.end_date for day in relevant_dates)
    ]
    return {
        "user_talk_messages": user_talk,
        "agent_roster_changes": sorted(raw_joins, key=lambda row: row["timestamp"]) + roster_changes,
        "agent_departure_source_limitation": "agents.jsonl.gz records export-time participation but no departure timestamp; dated departures are included only when documented in the CHANGELOG roster.",
        "village_goal_boundaries": goal_boundaries,
        "scaffolding_changes": scaffolding,
        "date_precision_note": "CHANGELOG and roster dates are date-level context only; coincidence with a context packet is not evidence of causation.",
    }


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    raise TypeError(f"cannot serialize {type(value)!r}")


def _escape(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("|", "\\|").replace("\r", "").replace("\n", "<br>")


def _external_markdown(external: Mapping[str, Any]) -> list[str]:
    lines = ["#### USER_TALK / administrator-channel messages", ""]
    messages = external["user_talk_messages"]
    if messages:
        lines.extend(["| Timestamp | Speaker | Canonical ID | Text |", "| --- | --- | --- | --- |"]) 
        for row in messages:
            lines.append(f"| {_escape(row['timestamp'])} | {_escape(row['agent_name'])} | `{row['canonical_event_id']}` | {_escape(row['chat_text'])} |")
    else:
        lines.append("None in this context interval.")
    lines.extend(["", "#### Agent roster joins/departures", ""])
    changes = external["agent_roster_changes"]
    if changes:
        lines.extend(["| Time/date | Change | Agent | Model | Source | Precision | Proximity |", "| --- | --- | --- | --- | --- | --- | --- |"])
        for row in changes:
            when = row.get("timestamp") or row.get("date")
            if row.get("minutes_from_boundary") is not None:
                proximity = f"{row['minutes_from_boundary']:+.1f} min from boundary; within packet={row['within_context_interval']}"
            else:
                proximity = "same UTC date; exact time unavailable"
            lines.append(f"| {_escape(when)} | {row['change']} | {_escape(row['agent_name'])} | {_escape(row['model'])} | {_escape(row['source'])} | {row['precision']} | {proximity} |")
    else:
        lines.append("No roster change was found in the available timestamp- or date-level sources.")
    lines.extend(["", f"_Source limitation: {external['agent_departure_source_limitation']}_", "", "#### Village-goal boundaries", ""])
    boundaries = external["village_goal_boundaries"]
    if boundaries:
        lines.extend(["| Timestamp | Boundary | Goal ID | Goal |", "| --- | --- | --- | --- |"])
        for row in boundaries:
            lines.append(f"| {_escape(row['timestamp'])} | {row['boundary']} | `{row['village_goal_id']}` | {_escape(row['village_goal_text'])} |")
    else:
        lines.append("None in this context interval.")
    lines.extend(["", "#### Dated scaffolding changes", ""])
    scaffolding = external["scaffolding_changes"]
    if scaffolding:
        for row in scaffolding:
            lines.extend([f"- **{row['heading']}** (date-level): {_escape(row['details'])}"])
    else:
        lines.append("None dated to a day overlapping this context interval.")
    lines.extend(["", f"_{external['date_precision_note']}_", ""])
    return lines


def render_context_markdown(packet: Mapping[str, Any]) -> str:
    metadata = packet["metadata"]
    lines = [
        f"# Candidate context: {metadata['episode_goal']}",
        "",
        "These packets present records and coincident contextual changes for manual adjudication. They do not identify causes or assign social-process labels.",
        "",
        f"- Context before each boundary: {metadata['before_minutes']} minutes",
        f"- Context after each boundary: {metadata['after_minutes']} minutes",
        f"- Candidates: {len(packet['candidates'])}",
        "",
    ]
    for candidate in packet["candidates"]:
        lines.extend(
            [
                f"## Candidate {candidate['rank']}: {candidate['boundary'].isoformat()}",
                "",
                f"- Aggregate score: `{candidate['aggregate_score']:.6f}`",
                f"- Contributing components: `{candidate['contributing_components']}`",
                f"- Context interval: `[{candidate['context_start'].isoformat()}, {candidate['context_end'].isoformat()})`",
                f"- Records: {len(candidate['records'])}",
                "",
                "### Coincident external context",
                "",
            ]
        )
        lines.extend(_external_markdown(candidate["external_context"]))
        lines.extend(
            [
                "### Chronological evidence",
                "",
                "| Side | Timestamp | Event index | Agent / model | Source / kind | Action | Canonical / source ID | Room | Chat text or session goal |",
                "| --- | --- | ---: | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for row in candidate["records"]:
            actor = row["agent_name"] or ""
            if row["agent_model"]:
                actor += f" / {row['agent_model']}"
            source_kind = f"{row['source_table']} / {row['event_kind']}"
            ids = f"`{row['canonical_event_id']}`<br>`{row['source_row_id']}`"
            text = row["chat_text"] if row["chat_text"] is not None else row["session_goal"]
            lines.append(
                f"| {row['relation']} | {_escape(row['timestamp'])} | {_escape(row['event_index'])} | {_escape(actor)} | "
                f"{_escape(source_kind)} | {_escape(row['action_type'])} | {ids} | {_escape(row['room_id'])} | {_escape(text)} |"
            )
        lines.append("")
    return "\n".join(lines)


def export_candidate_context(
    *,
    canonical_path: Path,
    candidates_path: Path,
    raw_dir: Path,
    changelog_path: Path,
    output_markdown: Path,
    output_json: Path,
    before_minutes: int = 90,
    after_minutes: int = 90,
) -> dict[str, Any]:
    if before_minutes <= 0 or after_minutes <= 0:
        raise ValueError("context durations must be positive")
    canonical_rows = pq.read_table(canonical_path).to_pylist()
    candidate_rows = sorted(pq.read_table(candidates_path).to_pylist(), key=lambda row: row["rank"])
    agents = [row.record for row in iter_raw_rows(raw_dir, "agents")]
    village_goals = [row.record for row in iter_raw_rows(raw_dir, "village_goals")]
    changelog_text = changelog_path.read_text(encoding="utf-8")
    goal_ids = {row["village_goal_id"] for row in canonical_rows}
    goal_texts = {row["village_goal_text"] for row in canonical_rows}
    if len(goal_ids) != 1 or len(goal_texts) != 1:
        raise ValueError("canonical file must contain exactly one village goal")
    packet: dict[str, Any] = {
        "metadata": {
            "episode_goal_id": next(iter(goal_ids)),
            "episode_goal": next(iter(goal_texts)),
            "before_minutes": before_minutes,
            "after_minutes": after_minutes,
            "causal_interpretation": False,
            "social_process_labels": False,
        },
        "candidates": [],
    }
    for candidate in candidate_rows:
        boundary = candidate["transition_timestamp"]
        start, end, selected = select_context_records(
            canonical_rows,
            boundary,
            before_minutes=before_minutes,
            after_minutes=after_minutes,
        )
        records = [_record_view(row, boundary) for row in selected]
        external = _external_context(
            selected,
            boundary=boundary,
            start=start,
            end=end,
            changelog_text=changelog_text,
            agents=agents,
            village_goals=village_goals,
        )
        packet["candidates"].append(
            {
                "rank": candidate["rank"],
                "comparison_id": candidate["comparison_id"],
                "boundary": boundary,
                "aggregate_score": candidate["aggregate_score"],
                "contributing_components": candidate["contributing_components"],
                "context_start": start,
                "context_end": end,
                "records": records,
                "external_context": external,
            }
        )
    output_markdown.parent.mkdir(parents=True, exist_ok=True)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(packet, default=_json_default, indent=2, ensure_ascii=False), encoding="utf-8")
    output_markdown.write_text(render_context_markdown(packet), encoding="utf-8", newline="\n")
    return packet
