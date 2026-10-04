"""Validation and human-readable reporting for canonical episode data."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from .ingestion import Episode, IngestionError

IMPORTANT_FIELDS = (
    "event_index",
    "agent_id",
    "agent_name",
    "agent_model",
    "room_id",
    "computer_use_session_id",
    "chat_content",
    "session_goal",
    "event_content",
    "agent_goal_id",
)


def validate_canonical_rows(
    rows: Sequence[Mapping[str, Any]],
    episode: Episode,
    audit: Mapping[str, Any],
) -> dict[str, Any]:
    if not rows:
        raise IngestionError(f"episode {episode.id} produced no canonical rows")
    ids = [row["canonical_event_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise IngestionError("duplicate canonical_event_id values")
    for row in rows:
        timestamp = row["event_timestamp"]
        if not episode.contains(timestamp):
            raise IngestionError(f"row outside episode interval: {row['canonical_event_id']}")
        if row["village_goal_id"] != episode.id or row["village_goal_text"] != episode.goal:
            raise IngestionError(f"goal join mismatch: {row['canonical_event_id']}")
        if row["source_row_number"] < 1 or len(row["source_record_sha256"]) != 64:
            raise IngestionError(f"invalid provenance: {row['canonical_event_id']}")
    for previous, current in zip(rows, rows[1:]):
        if current["event_timestamp"] < previous["event_timestamp"]:
            raise IngestionError("canonical rows are not chronologically sorted")

    episode_mismatch_count = sum(audit["chat_mismatch_counts_episode"].values())
    if episode_mismatch_count:
        raise IngestionError(
            "episode-local chat/event field consistency failures: "
            f"{audit['chat_mismatch_examples_episode']}"
        )

    timestamps = [row["event_timestamp"] for row in rows]
    return {
        "unique_agents": sorted(
            {(row["agent_id"], row["agent_name"], row["agent_model"]) for row in rows if row["agent_id"]},
            key=lambda value: (value[1] or "", value[0]),
        ),
        "min_timestamp": min(timestamps),
        "max_timestamp": max(timestamps),
        "missingness": {field: sum(row[field] is None for row in rows) for field in IMPORTANT_FIELDS},
        "counts_by_source": Counter(row["source_table"] for row in rows),
        "counts_by_kind": Counter(row["event_kind"] for row in rows),
        "counts_by_action": Counter(row["action_type"] for row in rows if row["action_type"]),
    }


def _fmt_time(value: datetime | None) -> str:
    return value.isoformat().replace("+00:00", "Z") if value is not None else "open"


def _md_table(headers: Sequence[str], values: Sequence[Sequence[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in values:
        escaped = [str(value).replace("|", "\\|").replace("\n", " ") for value in row]
        lines.append("| " + " | ".join(escaped) + " |")
    return "\n".join(lines)


def _preview(value: Any, limit: int = 180) -> str:
    if value is None:
        return ""
    text = str(value).replace("\r", " ").replace("\n", " ")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def render_validation_report(
    rows: Sequence[Mapping[str, Any]],
    episode: Episode,
    audit: Mapping[str, Any],
    validation: Mapping[str, Any],
    parquet_path: Path,
) -> str:
    interval = f"[{_fmt_time(episode.start)}, {_fmt_time(episode.end)})" if episode.end else f"[{_fmt_time(episode.start)}, +∞)"
    source_count_rows = [[key, value] for key, value in audit["counts_before"].items()]
    retained_rows = []
    all_keys = sorted(set(validation["counts_by_source"]) | set(validation["counts_by_kind"]))
    for key in all_keys:
        retained_rows.append([key, validation["counts_by_source"].get(key, ""), validation["counts_by_kind"].get(key, "")])
    action_rows = [[key, value] for key, value in sorted(validation["counts_by_action"].items())]
    agent_rows = [[agent_id, name, model] for agent_id, name, model in validation["unique_agents"]]
    missing_rows = [
        [field, missing, len(rows), f"{missing / len(rows):.1%}"]
        for field, missing in validation["missingness"].items()
    ]

    examples = []
    for kind in ("chat_message", "computer_use_session_goal", "high_level_event"):
        candidates = [row for row in rows if row["event_kind"] == kind][:3]
        for row in candidates:
            text = row["chat_content"] or row["session_goal"] or row["event_content"] or row["event_summary"] or row["search_query"] or row["next_session_goal"]
            examples.append(
                [kind, row["canonical_event_id"], _fmt_time(row["event_timestamp"]), row["agent_name"] or row["speaker_name"] or "", row["action_type"] or "", _preview(text)]
            )

    extra_field_lines = []
    for table, fields in sorted(audit["extra_fields"].items()):
        if fields:
            extra_field_lines.append(f"- `{table}` additional top-level fields retained through provenance: {', '.join(f'`{field}`' for field in fields)}")
    if not extra_field_lines:
        extra_field_lines.append("- No unexpected top-level fields were observed in the streamed large tables.")

    ongoing_note = " This goal is ongoing in the export, so its upper bound is open." if episode.end is None else ""
    mismatch_all = sum(audit["chat_mismatch_counts"].values())
    mismatch_episode = sum(audit["chat_mismatch_counts_episode"].values())
    delta_all = audit["chat_timestamp_delta_us"]
    delta_episode = audit["chat_timestamp_delta_us_episode"]
    return f"""# Ingestion validation: {episode.goal}

Generated by the episode-generic SwarmLens ingestion pipeline.

## Selected episode

- Goal ID: `{episode.id}`
- Goal text: **{episode.goal}**
- Village ID: `{episode.village_id}`
- Authoritative interval: `{interval}` UTC.{ongoing_note}
- Episode slug: `{episode.slug}`
- Canonical dataset: `{parquet_path.as_posix()}`

## Source-row counts before filtering

{_md_table(["Source", "Rows"], source_count_rows)}

## Retained rows

Total canonical rows: **{len(rows)}**

{_md_table(["Source or kind", "Count by source", "Count by event kind"], retained_rows)}

### High-level action types

{_md_table(["Action type", "Rows"], action_rows)}

## Agents represented

Unique agents: **{len(agent_rows)}**

{_md_table(["Agent ID", "Name", "Model"], agent_rows)}

## Time coverage

- Minimum retained timestamp: `{_fmt_time(validation['min_timestamp'])}`
- Maximum retained timestamp: `{_fmt_time(validation['max_timestamp'])}`
- All timestamps passed the authoritative interval check.

## Important-field missingness

Missingness is structural for many fields because chat messages, session goals, and high-level events intentionally retain different semantics.

{_md_table(["Field", "Missing", "Total", "Percent"], missing_rows)}

## Integrity checks

- Canonical event IDs: unique.
- Source IDs: unique within each source table.
- `events.event_index`: unique across the full source.
- Agent foreign keys: resolved.
- Chat-message foreign keys: {len(audit['missing_chat_links_episode'])} episode-local failures; {len(audit['missing_chat_links'])} across the full export.
- Computer-use-session foreign keys: {len(audit['missing_session_links_episode'])} episode-local failures; {len(audit['missing_session_links'])} across the full export.
- Chat/event content, room, and actor consistency: {mismatch_episode} episode-local mismatches; {mismatch_all} across the full export. Counts by field across the export: `{audit['chat_mismatch_counts']}`.
- Linked event-minus-chat timestamp deltas are measured rather than assumed equal: episode count {delta_episode['count']}, range {delta_episode['min']} to {delta_episode['max']} microseconds; full-export count {delta_all['count']}, range {delta_all['min']} to {delta_all['max']} microseconds.
- Event-index timestamp ordering: {audit['ordering_inversions']} inversion(s) across the full events source.
- Canonical chronological ordering: passed.
- Parquet schema and row-count round trip: passed before publication.
- Provenance: every row has source file, one-based JSONL row number, source UUID, and SHA-256 of the original JSON object bytes.

## Representative records

Provider-specific raw model output is intentionally excluded. Text previews are truncated.

{_md_table(["Kind", "Canonical ID", "Timestamp", "Actor", "Action", "Text preview"], examples)}

## Ambiguities and schema observations

- `chat_messages` has no `village_id`; episode membership is therefore determined by its own timestamp within the selected goal interval, and the selected goal supplies the canonical village ID.
- Chat rows and their `AGENT_TALK`/`USER_TALK` events are intentionally separate canonical records, linked by explicit IDs and event indexes.
- Computer-use session creation goals and high-level session/consolidation events are intentionally separate records.
- Agent-goal metadata is assigned only by a temporal per-agent join. No match remains null; overlapping matches fail the build.
- Raw provider-shaped `events.data.output` is not parsed or copied. The source record is recoverable and verifiable from provenance.
- The full export contains {len(audit['missing_chat_links'])} unresolved chat links, all of which are reported even when they fall outside this episode. Episode-local failures are counted separately.
{chr(10).join(extra_field_lines)}
"""
