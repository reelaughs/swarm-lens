"""Compact, deterministic evidence briefs built from frozen candidates."""

from __future__ import annotations

import json
import re
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

import pyarrow.parquet as pq

COMPONENT_INDEX = re.compile(r"^[CI](\d+):")


def _as_time(value: str | datetime) -> datetime:
    return value if isinstance(value, datetime) else datetime.fromisoformat(value)


def _changes(candidate: Mapping[str, Any], component: str) -> list[dict[str, Any]]:
    value = candidate[f"{component}_changes_json"]
    return json.loads(value) if isinstance(value, str) else list(value)


def _provenance(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "canonical_event_id": record["canonical_event_id"],
        "source_table": record["source_table"],
        "source_row_id": record["source_row_id"],
        "event_index": record.get("event_index"),
    }


class EvidenceCollector:
    def __init__(self, records: Sequence[Mapping[str, Any]]) -> None:
        self.records = records
        self.by_canonical = {record["canonical_event_id"]: record for record in records}
        self.chat_by_event_source = {
            record["linked_high_level_event_id"]: record
            for record in records
            if record["event_kind"] == "chat_message" and record.get("linked_high_level_event_id")
        }
        self.items: OrderedDict[str, dict[str, Any]] = OrderedDict()

    def add_record(self, record: Mapping[str, Any], *, category: str, reason: str, metrics: Mapping[str, Any] | None = None) -> None:
        paired: Mapping[str, Any] | None = None
        if record["event_kind"] == "chat_message" and record.get("linked_high_level_event_id"):
            paired = self.by_canonical.get(f"events:{record['linked_high_level_event_id']}")
        elif record["event_kind"] == "high_level_event" and record.get("action_type") in {"AGENT_TALK", "USER_TALK"}:
            paired = self.chat_by_event_source.get(record["source_row_id"])
        chat_record = record if record["event_kind"] == "chat_message" else paired
        event_record = record if record["event_kind"] == "high_level_event" else paired
        key = (
            f"chat-pair:{event_record['source_row_id']}"
            if chat_record is not None and event_record is not None
            else record["canonical_event_id"]
        )
        if key not in self.items:
            primary = chat_record or record
            text = primary.get("chat_text") or primary.get("session_goal")
            self.items[key] = {
                "display_key": key,
                "timestamp": primary["timestamp"],
                "relation": primary["relation"],
                "agent_name": primary.get("agent_name"),
                "agent_model": primary.get("agent_model"),
                "event_kind": "logical_chat" if chat_record is not None and event_record is not None else primary["event_kind"],
                "action_type": event_record.get("action_type") if event_record is not None else primary.get("action_type"),
                "room_id": primary.get("room_id") or (event_record.get("room_id") if event_record else None),
                "text": text,
                "categories": [],
                "selection_reasons": [],
                "selection_metrics": [],
                "provenance": [_provenance(value) for value in (chat_record, event_record) if value is not None]
                if chat_record is not None and event_record is not None
                else [_provenance(record)],
            }
        item = self.items[key]
        if category not in item["categories"]:
            item["categories"].append(category)
        if reason not in item["selection_reasons"]:
            item["selection_reasons"].append(reason)
        if metrics:
            item["selection_metrics"].append(dict(metrics))


def _component_index(label: str) -> int:
    match = COMPONENT_INDEX.match(label)
    if not match:
        raise ValueError(f"cannot parse NMF component label: {label!r}")
    return int(match.group(1)) - 1


def _nearest(records: Sequence[Mapping[str, Any]], boundary: datetime) -> Mapping[str, Any] | None:
    if not records:
        return None
    return min(
        records,
        key=lambda row: (
            abs((_as_time(row["timestamp"]) - boundary).total_seconds()),
            row.get("event_index") if row.get("event_index") is not None else 2**63 - 1,
            row["canonical_event_id"],
        ),
    )


def _deterministic_shift_description(changes: Mapping[str, Sequence[Mapping[str, Any]]]) -> list[str]:
    descriptions = []
    titles = {
        "communication": "Communication workstreams",
        "intention": "Intention workstreams",
        "participation": "Agent participation",
        "action_type": "Action types",
    }
    for component in ("communication", "intention", "participation", "action_type"):
        values = list(changes[component])
        increases = sorted((row for row in values if row["delta"] > 0), key=lambda row: (-row["delta"], row["label"]))
        decreases = sorted((row for row in values if row["delta"] < 0), key=lambda row: (row["delta"], row["label"]))
        parts = []
        if increases:
            parts.append(f"largest increase: {increases[0]['label']} ({increases[0]['delta']:+.3f})")
        if decreases:
            parts.append(f"largest decrease: {decreases[0]['label']} ({decreases[0]['delta']:+.3f})")
        descriptions.append(f"{titles[component]} — " + "; ".join(parts) if parts else f"{titles[component]} — no eligible change")
    return descriptions


def _context_flags(context: Mapping[str, Any], records: Sequence[Mapping[str, Any]]) -> list[str]:
    flags: set[str] = set()
    messages = context["user_talk_messages"]
    for message in messages:
        name = (message.get("agent_name") or "").casefold()
        text = (message.get("chat_text") or "").casefold()
        if name == "automated" or "automated nudge" in text:
            flags.add("AUTOMATED_NUDGE_NEARBY")
        else:
            flags.add("HUMAN_INTERVENTION_NEARBY")
    for change in context["agent_roster_changes"]:
        if change["change"] == "join":
            flags.add("AGENT_JOIN_NEARBY" if change.get("within_context_interval") else "AGENT_JOIN_SAME_DAY")
        elif change["change"] == "departure":
            flags.add("AGENT_DEPARTURE_NEARBY" if change.get("within_context_interval") else "AGENT_DEPARTURE_SAME_DAY")
    if context["scaffolding_changes"]:
        flags.add("SCAFFOLD_CHANGE_SAME_DAY")
    if context["village_goal_boundaries"]:
        flags.add("GOAL_BOUNDARY_NEARBY")
    if any(
        record["event_kind"] == "computer_use_session_goal"
        or record.get("action_type") in {"CONSOLIDATE", "START_USING_COMPUTER", "STOP_USING_COMPUTER"}
        for record in records
    ):
        flags.add("SESSION_BOUNDARY_NEARBY")
    return sorted(flags)


def _external_display_items(context: Mapping[str, Any]) -> list[dict[str, Any]]:
    items = []
    for change in context["agent_roster_changes"]:
        items.append(
            {
                "type": "agent_roster_change",
                "description": f"{change['change']}: {change['agent_name']} ({change['model']})",
                "time_or_date": str(change.get("timestamp") or change.get("date")),
                "precision": change["precision"],
                "provenance": change["source"],
                "minutes_from_boundary": change.get("minutes_from_boundary"),
            }
        )
    for boundary in context["village_goal_boundaries"]:
        items.append(
            {
                "type": "village_goal_boundary",
                "description": f"goal {boundary['boundary']}: {boundary['village_goal_text']}",
                "time_or_date": str(boundary["timestamp"]),
                "precision": "timestamp",
                "provenance": f"village_goals.jsonl.gz:{boundary['village_goal_id']}",
                "minutes_from_boundary": None,
            }
        )
    for change in context["scaffolding_changes"]:
        items.append(
            {
                "type": "scaffolding_change",
                "description": f"{change['heading']}: {change['details']}",
                "time_or_date": change["start_date"],
                "precision": "date",
                "provenance": f"CHANGELOG.md:{change['heading']}",
                "minutes_from_boundary": None,
            }
        )
    return items


def build_candidate_brief(
    *,
    context_packet: Mapping[str, Any],
    candidate_rows: Sequence[Mapping[str, Any]],
    topic_feature_rows: Sequence[Mapping[str, Any]],
    full_context_reference: str,
    changed_topic_components: int = 3,
    changed_agents: int = 3,
    changed_action_types: int = 3,
) -> dict[str, Any]:
    candidates_by_rank = {row["rank"]: row for row in candidate_rows}
    topic_weights = {
        (row["modality"], row["canonical_event_id"]): row["weights"]
        for row in topic_feature_rows
    }
    result: dict[str, Any] = {
        "metadata": {
            **context_packet["metadata"],
            "selection_method": {
                "changed_topic_components": changed_topic_components,
                "representatives_per_component_per_side": 1,
                "changed_agents": changed_agents,
                "changed_action_types": changed_action_types,
                "topic_representative_rule": "highest NMF document loading; ties by timestamp then canonical ID",
                "participation_action_rule": "nearest matching record to boundary on the side with the larger distribution share",
                "linked_chat_rule": "chat_message and linked AGENT_TALK/USER_TALK are one display item with both provenance records",
            },
            "detector_modified": False,
        },
        "candidates": [],
    }
    for context_candidate in context_packet["candidates"]:
        candidate = candidates_by_rank[context_candidate["rank"]]
        boundary = _as_time(context_candidate["boundary"])
        records = context_candidate["records"]
        collector = EvidenceCollector(records)
        changes = {component: _changes(candidate, component) for component in ("communication", "intention", "participation", "action_type")}

        for modality, event_kind in (("communication", "chat_message"), ("intention", "computer_use_session_goal")):
            for change in changes[modality][:changed_topic_components]:
                component_index = _component_index(change["label"])
                for side in ("before", "after"):
                    eligible = [
                        record
                        for record in records
                        if record["relation"] == side
                        and record["event_kind"] == event_kind
                        and (modality != "communication" or record.get("agent_id"))
                        and (modality, record["canonical_event_id"]) in topic_weights
                    ]
                    eligible.sort(
                        key=lambda record: (
                            -topic_weights[(modality, record["canonical_event_id"])][component_index],
                            _as_time(record["timestamp"]),
                            record["canonical_event_id"],
                        )
                    )
                    if eligible:
                        loading = topic_weights[(modality, eligible[0]["canonical_event_id"])][component_index]
                        collector.add_record(
                            eligible[0],
                            category=f"{modality}_representative",
                            reason=f"highest-loading {side} record for changed component {change['label']}",
                            metrics={"component": change["label"], "component_delta": change["delta"], "loading": loading, "side": side},
                        )

        for change in changes["participation"][:changed_agents]:
            side = "after" if change["delta"] >= 0 else "before"
            representative = _nearest(
                [
                    record
                    for record in records
                    if record["relation"] == side
                    and record["event_kind"] == "high_level_event"
                    and record.get("agent_name") == change["label"]
                ],
                boundary,
            )
            if representative:
                collector.add_record(
                    representative,
                    category="participation_representative",
                    reason=f"nearest {side} high-level event for agent with participation delta {change['delta']:+.3f}",
                    metrics={"agent": change["label"], "before": change["before"], "after": change["after"], "delta": change["delta"]},
                )

        for change in changes["action_type"][:changed_action_types]:
            side = "after" if change["delta"] >= 0 else "before"
            representative = _nearest(
                [
                    record
                    for record in records
                    if record["relation"] == side
                    and record["event_kind"] == "high_level_event"
                    and record.get("action_type") == change["label"]
                ],
                boundary,
            )
            if representative:
                collector.add_record(
                    representative,
                    category="action_type_representative",
                    reason=f"nearest {side} event for action type with delta {change['delta']:+.3f}",
                    metrics={"action_type": change["label"], "before": change["before"], "after": change["after"], "delta": change["delta"]},
                )

        user_messages = context_candidate["external_context"]["user_talk_messages"]
        automated = []
        human = []
        for message in user_messages:
            text = (message.get("chat_text") or "").casefold()
            target = automated if (message.get("agent_name") or "").casefold() == "automated" or "automated nudge" in text else human
            target.append(message)
        for label, messages, limit in (("automated_nudge", automated, 2), ("human_intervention", human, 3)):
            for message in sorted(messages, key=lambda row: (abs((_as_time(row["timestamp"]) - boundary).total_seconds()), row["canonical_event_id"]))[:limit]:
                collector.add_record(message, category="external_context", reason=f"nearest {label} USER_TALK record")

        session_record = _nearest(
            [
                record
                for record in records
                if record["event_kind"] == "computer_use_session_goal"
                or record.get("action_type") in {"CONSOLIDATE", "START_USING_COMPUTER", "STOP_USING_COMPUTER"}
            ],
            boundary,
        )
        if session_record:
            collector.add_record(session_record, category="external_context", reason="nearest session boundary record")

        evidence_items = list(collector.items.values())
        evidence_items.sort(key=lambda row: (_as_time(row["timestamp"]), row["display_key"]))
        external_items = _external_display_items(context_candidate["external_context"])
        result["candidates"].append(
            {
                "rank": candidate["rank"],
                "comparison_id": candidate["comparison_id"],
                "turning_point_timestamp": candidate["transition_timestamp"],
                "aggregate_score": candidate["aggregate_score"],
                "component_scores": {
                    component: {"js": candidate[f"{component}_js"], "standardized": candidate[f"{component}_z"]}
                    for component in ("communication", "intention", "participation", "action_type")
                },
                "contributing_components": candidate["contributing_components"].split(","),
                "deterministic_change_description": _deterministic_shift_description(changes),
                "largest_changes": changes,
                "context_flags": _context_flags(context_candidate["external_context"], records),
                "external_context_events": external_items,
                "evidence_items": evidence_items,
                "displayed_evidence_item_count": len(evidence_items) + len(external_items),
                "full_context_reference": f"{full_context_reference}#candidate-{candidate['rank']}",
            }
        )
    return result


def _escape(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("|", "\\|").replace("\r", "").replace("\n", "<br>")


def _excerpt(value: str | None, limit: int = 500) -> str:
    if not value:
        return ""
    compact = value.replace("\r", " ").replace("\n", " ")
    return compact if len(compact) <= limit else compact[: limit - 1] + "…"


def render_candidate_brief(brief: Mapping[str, Any]) -> str:
    lines = [
        f"# Candidate brief: {brief['metadata']['episode_goal']}",
        "",
        "This deterministic orientation layer summarizes distribution changes and selected evidence. Flags and external events are descriptive coincidences only; they do not alter detector scores or assert causes.",
        "",
    ]
    for candidate in brief["candidates"]:
        lines.extend(
            [
                f"## Candidate {candidate['rank']}: {candidate['turning_point_timestamp']}",
                "",
                f"- Aggregate score: **{candidate['aggregate_score']:.3f}**",
                f"- Context flags: `{', '.join(candidate['context_flags']) or 'none'}`",
                f"- Displayed evidence items: {candidate['displayed_evidence_item_count']}",
                f"- Full forensic packet: [{candidate['full_context_reference']}]({candidate['full_context_reference']})",
                "",
                "### Component scores",
                "",
                "| Component | JS divergence | Standardized |",
                "| --- | ---: | ---: |",
            ]
        )
        for component, scores in candidate["component_scores"].items():
            lines.append(f"| {component.replace('_', ' ')} | {scores['js']:.3f} | {scores['standardized']:.3f} |")
        lines.extend(["", "### Deterministic change description", ""])
        lines.extend(f"- {description}" for description in candidate["deterministic_change_description"])
        lines.extend(["", "### Coincident external context", ""])
        if candidate["external_context_events"]:
            lines.extend(["| Type | Time/date | Description | Precision | Provenance |", "| --- | --- | --- | --- | --- |"])
            for item in candidate["external_context_events"]:
                lines.append(f"| {item['type']} | {_escape(item['time_or_date'])} | {_escape(item['description'])} | {item['precision']} | `{_escape(item['provenance'])}` |")
        else:
            lines.append("No roster, goal-boundary, or dated-scaffolding context item matched this candidate.")

        lines.extend(["", "### Largest distribution changes", ""])
        for component, title in (
            ("communication", "Communication workstreams"),
            ("intention", "Intention workstreams"),
            ("participation", "Agent participation"),
            ("action_type", "Action types"),
        ):
            lines.extend([f"#### {title}", "", "| Item | Before | After | Δ |", "| --- | ---: | ---: | ---: |"])
            for item in candidate["largest_changes"][component]:
                lines.append(f"| {_escape(item['label'])} | {item['before']:.3f} | {item['after']:.3f} | {item['delta']:+.3f} |")
            lines.append("")

        lines.extend(
            [
                "### Selected evidence",
                "",
                "| Time | Side | Agent | Kind / action | Selection reason | Evidence excerpt | Provenance IDs |",
                "| --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for item in candidate["evidence_items"]:
            provenance = "<br>".join(
                f"`{source['canonical_event_id']}` / `{source['source_row_id']}` / idx `{source['event_index']}`"
                for source in item["provenance"]
            )
            lines.append(
                f"| {_escape(item['timestamp'])} | {item['relation']} | {_escape(item['agent_name'])} | "
                f"{_escape(item['event_kind'])} / {_escape(item['action_type'])} | {_escape('; '.join(item['selection_reasons']))} | "
                f"{_escape(_excerpt(item['text']))} | {provenance} |"
            )
        lines.append("")
    return "\n".join(lines)


def export_candidate_brief(
    *,
    context_json: Path,
    candidates_path: Path,
    topic_features_path: Path,
    output_markdown: Path,
    output_json: Path,
    full_context_reference: str = "candidate_context.md",
) -> dict[str, Any]:
    context_packet = json.loads(context_json.read_text(encoding="utf-8"))
    candidates = pq.read_table(candidates_path).to_pylist()
    topic_features = pq.read_table(topic_features_path).to_pylist()
    brief = build_candidate_brief(
        context_packet=context_packet,
        candidate_rows=candidates,
        topic_feature_rows=topic_features,
        full_context_reference=full_context_reference,
    )
    output_json.write_text(json.dumps(brief, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    output_markdown.write_text(render_candidate_brief(brief), encoding="utf-8", newline="\n")
    return brief
