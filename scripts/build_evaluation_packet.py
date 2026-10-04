"""Build a deterministic, read-only evaluation packet from frozen SwarmLens artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import pyarrow.parquet as pq


ABSENT = {"status": "absent_in_frozen_artifact"}
EPISODE_SLUG = "perform-novel-research"
EXPECTED_RANKS = [1, 2, 3, 4, 5]


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return None if math.isnan(value) else value
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "item"):
        return json_safe(value.item())
    return str(value)


def keep_first(items: list[Any], limit: int) -> dict[str, Any]:
    """Retain a deterministic prefix and explicitly record omitted item count."""
    return {
        "total_count": len(items),
        "retained_count": min(len(items), limit),
        "items": items[:limit],
        "omitted_count": max(0, len(items) - limit),
    }


def compact_uptake(value: dict[str, Any]) -> dict[str, Any]:
    result = {key: item for key, item in value.items() if key != "highest_scoring_matches"}
    result["representative_highest_scoring_matches"] = keep_first(
        value.get("highest_scoring_matches", []), 3
    )
    return result


def compact_follow_through(value: dict[str, Any]) -> dict[str, Any]:
    excluded = {"qualifying_semantic_matches", "linked_actions"}
    result = {key: item for key, item in value.items() if key not in excluded}
    result["representative_qualifying_semantic_matches"] = keep_first(
        value.get("qualifying_semantic_matches", []), 3
    )
    result["representative_linked_actions"] = keep_first(value.get("linked_actions", []), 3)
    return result


def compact_ranked_event(event: dict[str, Any]) -> dict[str, Any]:
    result = {
        key: item
        for key, item in event.items()
        if key not in {"uptake", "behavioral_follow_through"}
    }
    result["uptake"] = compact_uptake(event.get("uptake", {}))
    result["behavioral_follow_through"] = compact_follow_through(
        event.get("behavioral_follow_through", {})
    )
    return result


def compact_actor_structure(value: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for phase in ("antecedent", "followup"):
        phase_value = value.get(phase, {})
        phase_result: dict[str, Any] = {}
        for key, item in phase_value.items():
            if key == "concentration" and isinstance(item, dict):
                phase_result[key] = {
                    field: field_value
                    for field, field_value in item.items()
                    if field != "agent_activity_shares"
                }
            elif key == "coactivity" and isinstance(item, dict):
                phase_result[key] = {
                    field: field_value
                    for field, field_value in item.items()
                    if field not in {"recurring_pairs", "recurring_larger_sets"}
                }
                phase_result[key]["representative_recurring_pairs"] = keep_first(
                    item.get("recurring_pairs", []), 3
                )
                phase_result[key]["representative_recurring_larger_sets"] = keep_first(
                    item.get("recurring_larger_sets", []), 3
                )
            else:
                phase_result[key] = item
        result[phase] = phase_result
    result["changes"] = value.get("changes", ABSENT)
    return result


def compact_explicit_addresses(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "explicit_address_edge_count": value.get("explicit_address_edge_count", ABSENT),
        "representative_edges": keep_first(value.get("edges", []), 5),
    }


def compact_role_task_asymmetry(value: dict[str, Any]) -> dict[str, Any]:
    def compact(node: Any) -> Any:
        if isinstance(node, list):
            if node and all(isinstance(item, dict) for item in node):
                return keep_first(node, 5)
            return node
        if isinstance(node, dict):
            return {key: compact(item) for key, item in node.items()}
        return node

    return compact(value)


def collect_evidence_ids(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for item in value.values():
            found.update(collect_evidence_ids(item))
    elif isinstance(value, list):
        for item in value:
            found.update(collect_evidence_ids(item))
    elif isinstance(value, str) and value.startswith(("swl-e-", "swl-d-", "swl-c-")):
        found.add(value)
    return found


def evidence_catalog(bundle: dict[str, Any]) -> dict[str, dict[str, Any]]:
    catalog: dict[str, dict[str, Any]] = {}
    observations = bundle["deterministic_observations"]
    for category in ("raw_record_evidence", "derived_measurements", "contextual_observations"):
        for record in observations.get(category, []):
            evidence_id = record["evidence_id"]
            if evidence_id in catalog:
                raise ValueError(f"Duplicate evidence ID in bundle: {evidence_id}")
            catalog[evidence_id] = {"bundle_section": category, "evidence": record}
    return catalog


def load_attempts(cache_dir: Path, root: Path) -> dict[str, Any]:
    metadata_paths = sorted(cache_dir.glob("generations/generation_*/attempt_*/response_metadata.json"))
    attempts = []
    cumulative = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    for metadata_path in metadata_paths:
        metadata = read_json(metadata_path)
        usage = metadata.get("usage", {})
        normalized_usage = {
            "input_tokens": int(usage.get("input_tokens", 0)),
            "output_tokens": int(usage.get("output_tokens", 0)),
            "total_tokens": int(usage.get("total_tokens", 0)),
        }
        for key in cumulative:
            cumulative[key] += normalized_usage[key]
        validation_path = metadata_path.parent / "validation_errors.json"
        attempts.append(
            {
                "attempt": len(attempts) + 1,
                "model": metadata.get("model", ABSENT),
                "usage": normalized_usage,
                "validation_errors": read_json(validation_path) if validation_path.exists() else [],
                "source_path": rel(metadata_path, root),
            }
        )
    if not attempts:
        raise ValueError(f"No generation attempts found in {cache_dir}")
    return {
        "attempt_count": len(attempts),
        "first_attempt_validated": not bool(attempts[0]["validation_errors"]),
        "repair_required": len(attempts) > 1,
        "cumulative_usage": cumulative,
        "attempts": attempts,
    }


def find_frozen_stage4_caches(
    cache_root: Path, frozen_identity: dict[str, Any]
) -> dict[int, Path]:
    identity_fields = (
        "stage3_sha256",
        "configuration_sha256",
        "hypothesis_library_sha256",
        "system_prompt_sha256",
        "developer_prompt_sha256",
        "response_schema_sha256",
        "provider",
        "model",
        "reasoning_effort",
        "store",
        "max_output_tokens",
    )
    matches: dict[int, Path] = {}
    for identity_path in sorted(cache_root.glob("*/candidate_*/request_identity.json")):
        identity = read_json(identity_path)
        if all(identity.get(key) == frozen_identity.get(key) for key in identity_fields):
            rank = int(identity["candidate_rank"])
            validated_path = identity_path.parent / "validated_interpretation.json"
            if validated_path.exists():
                if rank in matches:
                    raise ValueError(f"Multiple frozen Stage 4 caches found for Candidate {rank}")
                matches[rank] = identity_path.parent
    if sorted(matches) != EXPECTED_RANKS:
        raise ValueError(f"Expected frozen Stage 4 caches for ranks 1-5; found {sorted(matches)}")
    return matches


def build_packet(root: Path) -> dict[str, Any]:
    episode_root = root / "outputs" / "episodes" / EPISODE_SLUG
    tp_root = episode_root / "turning_points"
    paths = {
        "ingestion_validation": episode_root / "ingestion_validation.md",
        "canonical_events": root / "data" / "processed" / "episodes" / EPISODE_SLUG / "events.parquet",
        "stage2_configuration": tp_root / "resolved_configuration.json",
        "stage2_candidates": tp_root / "top_candidates.parquet",
        "stage2_report": tp_root / "report.md",
        "stage25_brief": tp_root / "candidate_brief.json",
        "stage25_context": tp_root / "candidate_context.json",
        "stage3": tp_root / "evidence_reconstruction" / "evidence_reconstruction.json",
        "stage4_latest": tp_root / "interpretation" / "interpretation.json",
    }
    missing = [str(path) for path in paths.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Required frozen artifact(s) missing: {missing}")

    stage2_config = read_json(paths["stage2_configuration"])
    brief = read_json(paths["stage25_brief"])
    stage3 = read_json(paths["stage3"])
    latest_stage4 = read_json(paths["stage4_latest"])
    frozen_identity = latest_stage4["metadata"]["input_identity"]
    caches = find_frozen_stage4_caches(
        root / "data" / "interim" / "episodes" / EPISODE_SLUG / "interpretation",
        frozen_identity,
    )

    candidate_rows = sorted(
        pq.read_table(paths["stage2_candidates"]).to_pylist(), key=lambda item: item["rank"]
    )
    event_rows = pq.read_table(
        paths["canonical_events"],
        columns=[
            "event_timestamp",
            "event_kind",
            "agent_id",
            "village_goal_start",
            "village_goal_end",
        ],
    ).to_pylist()
    stage2_by_rank = {
        int(row["rank"]): json_safe(row) for row in candidate_rows
    }
    brief_by_rank = {int(item["rank"]): item for item in brief["candidates"]}
    stage3_by_rank = {int(item["rank"]): item for item in stage3["candidates"]}
    if sorted(stage2_by_rank) != EXPECTED_RANKS:
        raise ValueError(f"Stage 2 ranks are not 1-5: {sorted(stage2_by_rank)}")
    if sorted(brief_by_rank) != EXPECTED_RANKS or sorted(stage3_by_rank) != EXPECTED_RANKS:
        raise ValueError("Stage 2.5 or Stage 3 is missing a frozen candidate rank")

    candidates: list[dict[str, Any]] = []
    usage_summary: list[dict[str, Any]] = []
    for rank in EXPECTED_RANKS:
        stage2_row = stage2_by_rank[rank]
        brief_candidate = brief_by_rank[rank]
        stage3_candidate = stage3_by_rank[rank]
        cache_dir = caches[rank]
        validated_path = cache_dir / "validated_interpretation.json"
        bundle_path = cache_dir / "input_evidence_bundle.json"
        identity_path = cache_dir / "request_identity.json"
        validated = read_json(validated_path)
        bundle = read_json(bundle_path)
        identity = read_json(identity_path)
        attempts = load_attempts(cache_dir, root)

        comparison_ids = {
            stage2_row["comparison_id"],
            brief_candidate["comparison_id"],
            stage3_candidate["comparison_id"],
            validated["comparison_id"],
        }
        if len(comparison_ids) != 1:
            raise ValueError(f"Candidate {rank} comparison IDs disagree: {comparison_ids}")
        if validated["behavioral_change_rank"] != rank or identity["candidate_rank"] != rank:
            raise ValueError(f"Candidate {rank} Stage 4 rank identity mismatch")
        if bundle.get("bundle_version") != "2.0":
            raise ValueError(f"Candidate {rank} is not evidence bundle v2.0")
        if validated["interpretation"].get("schema_version") != "1.2":
            raise ValueError(f"Candidate {rank} is not interpretation schema 1.2")
        if not (
            bundle.get("evidence_bundle_sha256") == identity["evidence_bundle_sha256"]
            == validated.get("evidence_bundle_sha256")
        ):
            raise ValueError(f"Candidate {rank} evidence-bundle identity mismatch")

        referenced_ids = sorted(collect_evidence_ids(validated["interpretation"]))
        catalog = evidence_catalog(bundle)
        provenance = bundle["evidence_id_to_provenance"]
        missing_ids = [evidence_id for evidence_id in referenced_ids if evidence_id not in catalog]
        missing_provenance = [evidence_id for evidence_id in referenced_ids if evidence_id not in provenance]
        if missing_ids or missing_provenance:
            raise ValueError(
                f"Candidate {rank} incomplete evidence mapping: "
                f"missing records={missing_ids}, missing provenance={missing_provenance}"
            )
        evidence_mapping = {
            evidence_id: {
                **catalog[evidence_id],
                "provenance": provenance[evidence_id],
            }
            for evidence_id in referenced_ids
        }

        ranked_events = [compact_ranked_event(item) for item in stage3_candidate["ranked_preceding_events"]]
        candidate = {
            "stage2_rank": rank,
            "comparison_id": stage2_row["comparison_id"],
            "turning_point_timestamp": stage3_candidate["turning_point_timestamp"],
            "stage2": {
                "aggregate_detector_score": stage2_row["aggregate_score"],
                "component_signal_changes_and_scores": {
                    component: {
                        "eligible": stage2_row[f"{component}_eligible"],
                        "jensen_shannon_divergence": stage2_row[f"{component}_js"],
                        "standardized_score": stage2_row[f"{component}_z"],
                    }
                    for component in ("communication", "intention", "participation", "action_type")
                },
                "contributing_components": stage2_row["contributing_components"],
                "contributing_component_count": stage2_row["contributing_component_count"],
                "window_size_reliable": stage2_row["window_size_reliable"],
                "activity_and_coverage_diagnostics": {
                    key: stage2_row[key]
                    for key in (
                        "window_size_minutes",
                        "before_window_start",
                        "before_window_end",
                        "after_window_start",
                        "after_window_end",
                        "before_event_count",
                        "after_event_count",
                        "before_agent_chat_count",
                        "after_agent_chat_count",
                        "before_session_count",
                        "after_session_count",
                        "before_agent_event_count",
                        "after_agent_event_count",
                        "before_distinct_agents",
                        "after_distinct_agents",
                    )
                },
                "largest_distribution_changes": brief_candidate.get("largest_changes", ABSENT),
            },
            "stage2_5": {
                "contextual_flags": brief_candidate.get("context_flags", ABSENT),
                "deterministic_change_description": brief_candidate.get(
                    "deterministic_change_description", ABSENT
                ),
                "external_context_events": brief_candidate.get("external_context_events", ABSENT),
                "compact_evidence_brief": brief_candidate.get("evidence_items", ABSENT),
                "displayed_evidence_item_count": brief_candidate.get(
                    "displayed_evidence_item_count", ABSENT
                ),
                "full_context_reference": brief_candidate.get("full_context_reference", ABSENT),
            },
            "stage3": {
                "windows_and_coverage": stage3_candidate.get("windows", ABSENT),
                "semantic_thresholds": stage3_candidate.get("semantic_thresholds", ABSENT),
                "ranked_preceding_evidence": ranked_events,
                "follow_through_and_uptake_observations": [
                    {
                        "preceding_event_rank": item.get("preceding_event_rank", ABSENT),
                        "logical_item_id": item.get("logical_item_id", ABSENT),
                        "uptake_summary": {
                            key: value
                            for key, value in item.get("uptake", {}).items()
                            if key != "representative_highest_scoring_matches"
                        },
                        "behavioral_follow_through_summary": {
                            key: value
                            for key, value in item.get("behavioral_follow_through", {}).items()
                            if key
                            not in {
                                "representative_qualifying_semantic_matches",
                                "representative_linked_actions",
                            }
                        },
                        "persistence": item.get("persistence", ABSENT),
                        "population_level_alignment": item.get(
                            "population_level_alignment", ABSENT
                        ),
                    }
                    for item in ranked_events
                ],
                "persistence_observations": stage3_candidate.get(
                    "persistence_observations", ABSENT
                ),
                "structural_observations": {
                    "distinct_agents_in_reconstruction": stage3_candidate.get(
                        "distinct_agents_in_reconstruction", ABSENT
                    ),
                    "actor_and_structure": compact_actor_structure(
                        stage3_candidate.get("actor_and_structure", {})
                    ),
                    "explicit_address_relationships": compact_explicit_addresses(
                        stage3_candidate.get("explicit_address_relationships", {})
                    ),
                    "role_task_asymmetry": compact_role_task_asymmetry(
                        stage3_candidate.get("role_task_asymmetry", {})
                    ),
                    "relationship_to_stage2_signal": stage3_candidate.get(
                        "relationship_to_stage2_signal", ABSENT
                    ),
                },
                "external_context": stage3_candidate.get("external_context", ABSENT),
                "null_findings": stage3_candidate.get("null_findings", ABSENT),
                "caveats": stage3_candidate.get("caveats", ABSENT),
                "full_context_reference": stage3_candidate.get("full_context_reference", ABSENT),
            },
            "stage4": {
                "interpretation_status": validated.get("interpretation_status", ABSENT),
                "interpretation": validated["interpretation"],
                "model_response": validated.get("model_response", ABSENT),
                "validation_and_usage": attempts,
                "all_referenced_evidence_ids": referenced_ids,
                "referenced_evidence_and_provenance": evidence_mapping,
                "cache_identity": validated.get("cache_identity", identity),
                "evidence_bundle_file_sha256": sha256(bundle_path),
            },
            "source_paths": {
                "stage2_candidates": rel(paths["stage2_candidates"], root),
                "stage2_configuration": rel(paths["stage2_configuration"], root),
                "stage2_5_brief": rel(paths["stage25_brief"], root),
                "stage2_5_full_context": rel(paths["stage25_context"], root),
                "stage3_reconstruction": rel(paths["stage3"], root),
                "stage4_validated_interpretation": rel(validated_path, root),
                "stage4_evidence_bundle": rel(bundle_path, root),
                "stage4_request_identity": rel(identity_path, root),
            },
        }
        candidates.append(candidate)
        usage_summary.append(
            {
                "stage2_rank": rank,
                "repair_required": attempts["repair_required"],
                "first_attempt_validated": attempts["first_attempt_validated"],
                "token_usage": attempts["cumulative_usage"],
                "api_returned_models": sorted(
                    {str(item["model"]) for item in attempts["attempts"]}
                ),
            }
        )

    timestamps = [row["event_timestamp"] for row in event_rows]
    event_kind_counts = Counter(str(row["event_kind"]) for row in event_rows)
    goal_starts = {row["village_goal_start"] for row in event_rows}
    goal_ends = {row["village_goal_end"] for row in event_rows}
    if len(goal_starts) != 1 or len(goal_ends) != 1:
        raise ValueError("Canonical episode rows do not share one authoritative goal interval")
    authoritative_interval = {
        "start": next(iter(goal_starts)).isoformat(),
        "end": next(iter(goal_ends)).isoformat(),
        "filter_semantics": "[start, end)",
        "stage3_local_display": stage3["metadata"]["episode_interval"],
    }
    record_counts = {
        "total_canonical_records": len(event_rows),
        "by_event_kind": {
            key: value for key, value in sorted(event_kind_counts.items())
        },
        "unique_non_null_agents": len(
            {row["agent_id"] for row in event_rows if row["agent_id"] is not None}
        ),
        "minimum_record_timestamp": min(timestamps).isoformat(),
        "maximum_record_timestamp": max(timestamps).isoformat(),
    }
    stage4_hashes = dict(frozen_identity)
    stage4_hashes["schema_version"] = latest_stage4["metadata"]["schema_version"]
    stage4_hashes["prompt_version"] = latest_stage4["metadata"]["prompt_version"]
    stage4_hashes["hypothesis_library_version"] = latest_stage4["metadata"][
        "hypothesis_library_version"
    ]

    packet = {
        "packet_type": "frozen_evaluation_packet",
        "packet_version": "1.0",
        "packaging_scope": "Mechanical selection from frozen Stage 1-4 artifacts; no new evaluation or inference.",
        "episode": {
            "slug": EPISODE_SLUG,
            "goal_id": stage3["metadata"]["episode_goal_id"],
            "goal_text": stage3["metadata"]["episode_goal"],
            "authoritative_interval": authoritative_interval,
            "relevant_record_counts": record_counts,
            "frozen_stage2": {
                "configuration_sha256": stage2_config["configuration_sha256"],
                "resolved_configuration_artifact_sha256": sha256(paths["stage2_configuration"]),
                "resolved_configuration": stage2_config,
            },
            "frozen_stage3": {
                "configuration_sha256": stage3["metadata"]["configuration_sha256"],
                "artifact_sha256": sha256(paths["stage3"]),
                "input_identity": stage3["metadata"]["input_identity"],
            },
            "frozen_stage4": stage4_hashes,
            "stage4_candidate_repairs_models_and_usage": usage_summary,
        },
        "candidates": candidates,
        "source_paths": {key: rel(path, root) for key, path in paths.items()},
    }
    validate_packet(packet)
    return packet


def validate_packet(packet: dict[str, Any]) -> None:
    ranks = [item["stage2_rank"] for item in packet["candidates"]]
    if ranks != EXPECTED_RANKS:
        raise ValueError(f"Packet candidate order must be frozen Stage 2 ranks 1-5; got {ranks}")
    if packet["episode"]["goal_text"] != "Perform novel research!":
        raise ValueError("Wrong episode selected")
    seen_comparisons: set[str] = set()
    for candidate in packet["candidates"]:
        rank = candidate["stage2_rank"]
        comparison_id = candidate["comparison_id"]
        if comparison_id in seen_comparisons:
            raise ValueError(f"Duplicate candidate comparison ID: {comparison_id}")
        seen_comparisons.add(comparison_id)
        evidence_ids = candidate["stage4"]["all_referenced_evidence_ids"]
        mapping_ids = sorted(candidate["stage4"]["referenced_evidence_and_provenance"])
        if evidence_ids != mapping_ids:
            raise ValueError(f"Candidate {rank} Stage 4 evidence mapping is incomplete")
        for evidence_id, mapped in candidate["stage4"][
            "referenced_evidence_and_provenance"
        ].items():
            if mapped["evidence"].get("evidence_id") != evidence_id:
                raise ValueError(f"Candidate {rank} evidence record mismatch for {evidence_id}")
            if mapped.get("provenance") is None:
                raise ValueError(f"Candidate {rank} lacks provenance for {evidence_id}")


def text_excerpt(value: Any, limit: int = 600) -> str:
    if value is None:
        return "absent"
    text = " ".join(str(value).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def cell(value: Any, limit: int = 300) -> str:
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return text_excerpt(value, limit).replace("|", "\\|")


def bullets(values: Iterable[Any]) -> str:
    values = list(values)
    if not values:
        return "- None recorded."
    return "\n".join(f"- {cell(value, 1000)}" for value in values)


def render_markdown(packet: dict[str, Any]) -> str:
    episode = packet["episode"]
    lines = [
        "# Frozen evaluation packet: Perform novel research!",
        "",
        "> Mechanical packaging of frozen SwarmLens Stage 1–4 outputs. This packet does not add an evaluation, causal attribution, or new inference.",
        "",
        "## Episode and frozen identities",
        "",
        f"- Goal ID: `{episode['goal_id']}`",
        f"- Authoritative interval: `{episode['authoritative_interval']['start']}` to `{episode['authoritative_interval']['end']}` (`[start, end)`)",
        f"- Canonical records: `{episode['relevant_record_counts']['total_canonical_records']}`",
        f"- Records by event kind: `{json.dumps(episode['relevant_record_counts']['by_event_kind'], sort_keys=True)}`",
        f"- Unique non-null agents: `{episode['relevant_record_counts']['unique_non_null_agents']}`",
        f"- Stage 2 configuration hash: `{episode['frozen_stage2']['configuration_sha256']}`",
        f"- Stage 3 configuration hash: `{episode['frozen_stage3']['configuration_sha256']}`",
        f"- Stage 3 artifact hash: `{episode['frozen_stage3']['artifact_sha256']}`",
        f"- Stage 4 model: `{episode['frozen_stage4']['model']}`",
        f"- Stage 4 schema/config/library/prompt hashes: `{episode['frozen_stage4']['response_schema_sha256']}` / `{episode['frozen_stage4']['configuration_sha256']}` / `{episode['frozen_stage4']['hypothesis_library_sha256']}` / `{episode['frozen_stage4']['system_prompt_sha256']}`, `{episode['frozen_stage4']['developer_prompt_sha256']}`",
        "",
        "### Stage 4 repair and usage summary",
        "",
        "| Rank | First attempt valid | Repair | Input tokens | Output tokens | Total tokens | API model(s) |",
        "|---:|:---:|:---:|---:|---:|---:|---|",
    ]
    for item in episode["stage4_candidate_repairs_models_and_usage"]:
        usage = item["token_usage"]
        lines.append(
            f"| {item['stage2_rank']} | {item['first_attempt_validated']} | {item['repair_required']} | "
            f"{usage['input_tokens']} | {usage['output_tokens']} | {usage['total_tokens']} | "
            f"{cell(item['api_returned_models'])} |"
        )

    for candidate in packet["candidates"]:
        rank = candidate["stage2_rank"]
        stage2 = candidate["stage2"]
        stage25 = candidate["stage2_5"]
        stage3 = candidate["stage3"]
        stage4 = candidate["stage4"]
        interpretation = stage4["interpretation"]
        social = interpretation["social_process_evaluation"]
        lines.extend(
            [
                "",
                f"## Candidate {rank}",
                "",
                f"- Turning point: `{candidate['turning_point_timestamp']}`",
                f"- Stage 2 comparison: `{candidate['comparison_id']}`",
                f"- Aggregate detector score: `{stage2['aggregate_detector_score']}`",
                f"- Stage 2.5 contextual flags: `{cell(stage25['contextual_flags'], 1000)}`",
                "",
                "### Stage 2 detector evidence",
                "",
                "| Signal | Eligible | Raw JS divergence | Standardized score |",
                "|---|:---:|---:|---:|",
            ]
        )
        for signal, values in stage2["component_signal_changes_and_scores"].items():
            lines.append(
                f"| {signal} | {values['eligible']} | {values['jensen_shannon_divergence']} | "
                f"{values['standardized_score']} |"
            )
        diagnostics = stage2["activity_and_coverage_diagnostics"]
        lines.extend(
            [
                "",
                f"Deterministic change description: {stage25['deterministic_change_description']}",
                "",
                "| Window | Events | Chats | Sessions | High-level events | Distinct agents |",
                "|---|---:|---:|---:|---:|---:|",
                f"| Before (`{diagnostics['before_window_start']}`–`{diagnostics['before_window_end']}`) | {diagnostics['before_event_count']} | {diagnostics['before_agent_chat_count']} | {diagnostics['before_session_count']} | {diagnostics['before_agent_event_count']} | {diagnostics['before_distinct_agents']} |",
                f"| After (`{diagnostics['after_window_start']}`–`{diagnostics['after_window_end']}`) | {diagnostics['after_event_count']} | {diagnostics['after_agent_chat_count']} | {diagnostics['after_session_count']} | {diagnostics['after_agent_event_count']} | {diagnostics['after_distinct_agents']} |",
                "",
                "Largest recorded distribution changes:",
                "",
                "```json",
                json.dumps(stage2["largest_distribution_changes"], indent=2, ensure_ascii=False),
                "```",
                "",
                "### Stage 2.5 compact evidence brief",
                "",
                "| Display ID | Time | Relation | Agent | Kind/action | Evidence excerpt | Provenance |",
                "|---|---|---|---|---|---|---|",
            ]
        )
        for item in stage25["compact_evidence_brief"]:
            provenance = item.get("provenance", {})
            lines.append(
                f"| `{item.get('display_key', 'absent')}` | {cell(item.get('timestamp'))} | "
                f"{cell(item.get('relation'))} | {cell(item.get('agent_name'))} | "
                f"{cell(item.get('event_kind'))}/{cell(item.get('action_type'))} | "
                f"{cell(item.get('text'), 600)} | {cell(provenance, 500)} |"
            )
        lines.extend(
            [
                "",
                "External/context events (coincident context only):",
                "",
                bullets(stage25["external_context_events"] if isinstance(stage25["external_context_events"], list) else [stage25["external_context_events"]]),
                "",
                "### Stage 3 process-neutral reconstruction",
                "",
                "| Preceding rank | Time | Agent | Label/support | Aggregate | Evidence excerpt | Uptake / follow-through |",
                "|---:|---|---|---|---:|---|---|",
            ]
        )
        for item in stage3["ranked_preceding_evidence"]:
            uptake = item.get("uptake", {})
            follow = item.get("behavioral_follow_through", {})
            lines.append(
                f"| {item.get('preceding_event_rank', 'absent')} | {cell(item.get('timestamp'))} | "
                f"{cell(item.get('agent_name'))} | {cell(item.get('evidence_label'))}; "
                f"{cell(item.get('antecedent_support'))} | {item.get('aggregate_score', 'absent')} | "
                f"{cell(item.get('text'), 600)} | other-agent uptake={uptake.get('matching_other_agent_count', 'absent')}; "
                f"follow-through={cell(follow.get('classification'))}; persistence={cell(item.get('persistence'), 250)} |"
            )
        lines.extend(
            [
                "",
                "Follow-through, uptake, and persistence observations are retained with representative raw matches in the JSON packet. Structural observations below are deterministic diagnostics; same-window co-activity is activity-density/context, not relational evidence.",
                "",
                "```json",
                json.dumps(
                    {
                        "persistence_observations": stage3["persistence_observations"],
                        "structural_observations": stage3["structural_observations"],
                        "external_context": stage3["external_context"],
                    },
                    indent=2,
                    ensure_ascii=False,
                ),
                "```",
                "",
                "Null findings:",
                "",
                bullets(stage3["null_findings"]),
                "",
                "Caveats:",
                "",
                bullets(stage3["caveats"]),
                "",
                "### Stage 4 constrained interpretation",
                "",
                f"Analyst note: {interpretation['analyst_note'].get('summary', interpretation['analyst_note']) if isinstance(interpretation['analyst_note'], dict) else interpretation['analyst_note']}",
                "",
                f"Social-process result: `{social['result']}`. {social.get('rationale', '')}",
                "",
            ]
        )
        hypotheses = social.get("hypotheses", [])
        if not hypotheses:
            lines.append("No candidate hypotheses were returned.")
        for hypothesis in hypotheses:
            lines.extend(
                [
                    f"#### {hypothesis['hypothesis_id']} — {hypothesis['interpretation_role']}",
                    "",
                    f"- Displayed confidence: `{hypothesis['displayed_confidence']}` (proposed `{hypothesis['proposed_confidence']}`; cap `{hypothesis.get('allowed_confidence_cap')}`)",
                    f"- Summary: {hypothesis['summary']}",
                    f"- Supported signatures ({hypothesis['supported_signature_count']}): `{cell(hypothesis['supported_signatures'], 2000)}`",
                    f"- Evidence groups ({hypothesis['independent_evidence_group_count']}; diversity `{hypothesis['evidence_diversity']}`): `{cell(hypothesis['evidence_groups'], 2500)}`",
                    f"- Correlated-evidence caveat: {cell(hypothesis.get('correlated_evidence_caveat', ABSENT), 1500)}",
                    f"- Counterevidence: `{cell(hypothesis.get('contradicted_counter_signatures', []), 2000)}`",
                    f"- Unknown signatures: `{cell(hypothesis.get('unknown_signature_ids', []), 1200)}`",
                    f"- Alternatives: `{cell(hypothesis.get('alternative_explanations', []), 2000)}`",
                    "",
                ]
            )
        lines.extend(
            [
                f"Comparative rationale: `{cell(social.get('comparative_rationale', ABSENT), 2500)}`",
                "",
                f"All Stage 4 referenced evidence IDs ({len(stage4['all_referenced_evidence_ids'])}): `{', '.join(stage4['all_referenced_evidence_ids'])}`",
                "",
                "#### Referenced evidence and provenance",
                "",
                "| Evidence ID | Bundle section | What the frozen item records | Provenance |",
                "|---|---|---|---|",
            ]
        )
        for evidence_id, mapped in stage4["referenced_evidence_and_provenance"].items():
            evidence = mapped["evidence"]
            description = evidence.get("text", evidence.get("description", evidence.get("measurement", ABSENT)))
            lines.append(
                f"| `{evidence_id}` | {mapped['bundle_section']} | {cell(description, 700)} | "
                f"{cell(mapped['provenance'], 700)} |"
            )
        lines.extend(
            [
                "",
                "Source artifacts:",
                "",
                *[f"- {key}: `{value}`" for key, value in candidate["source_paths"].items()],
            ]
        )

    lines.extend(
        [
            "",
            "## Packet source index",
            "",
            *[f"- {key}: `{value}`" for key, value in packet["source_paths"].items()],
            "",
            "The JSON companion retains the selected frozen structures, representative raw excerpts, every Stage 4-referenced evidence record, and its evidence-ID-to-provenance mapping.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    output_dir = root / "outputs" / "episodes" / EPISODE_SLUG / "evaluation_packet"
    output_dir.mkdir(parents=True, exist_ok=True)
    packet = build_packet(root)
    json_path = output_dir / "evaluation_packet.json"
    markdown_path = output_dir / "evaluation_packet.md"
    json_path.write_text(
        json.dumps(packet, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    markdown_path.write_text(render_markdown(packet), encoding="utf-8")
    print(f"Validated and wrote {rel(json_path, root)}")
    print(f"Validated and wrote {rel(markdown_path, root)}")


if __name__ == "__main__":
    main()
