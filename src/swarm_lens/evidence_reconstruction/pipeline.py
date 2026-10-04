"""End-to-end Stage 3 pipeline, separate from frozen Stage 1/2/2.5 outputs."""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

import joblib
import numpy as np
import pyarrow.parquet as pq

from .antecedents import candidate_component_scores, rank_preceding_events, stage2_distribution_changes
from .config import EvidenceReconstructionConfig
from .logical_items import build_logical_items
from .reporting import render_markdown
from .semantics import build_semantic_space
from .structure import (
    build_structural_windows,
    explicit_address_edges,
    specialization_summary,
    structural_summary,
)
from .windows import reconstruction_intervals


@dataclass(frozen=True)
class ReconstructionResult:
    output_json: Path
    output_markdown: Path
    cache_dir: Path
    cache_hit: bool
    candidate_count: int


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(f"cannot serialize {type(value)!r}")


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=_json_default), encoding="utf-8")


def _load_inactive_gaps(path: Path, window_minutes: int) -> list[dict[str, Any]]:
    rows = []
    with Path(path).open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            if int(row["window_size_minutes"]) == window_minutes:
                rows.append(
                    {
                        "start": datetime.fromisoformat(row["start"]),
                        "end": datetime.fromisoformat(row["end"]),
                        "duration_minutes": int(row["duration_minutes"]),
                    }
                )
    return rows


def _normalize_topic_vector(vector: np.ndarray) -> list[float] | None:
    total = float(vector.sum())
    return (vector / total).tolist() if total > 0 else None


def _topic_vectors_for_items(
    items: Sequence[Mapping[str, Any]],
    *,
    topic_weights: Mapping[tuple[str, str], Sequence[float]],
    stage2_cache_dir: Path,
) -> dict[str, list[float]]:
    vectorizers = {
        modality: joblib.load(stage2_cache_dir / f"{modality}_vectorizer.joblib")
        for modality in ("communication", "intention")
    }
    models = {modality: joblib.load(stage2_cache_dir / f"{modality}_nmf.joblib") for modality in ("communication", "intention")}
    result: dict[str, list[float]] = {}
    for item in items:
        modality = "communication" if item["source_type"] in {"chat", "user_talk"} else "intention" if item["source_type"] == "session_goal" else None
        if modality is None or not item.get("text"):
            continue
        canonical_ids = [row["canonical_event_id"] for row in item["provenance"]]
        cached = next((topic_weights[(modality, value)] for value in canonical_ids if (modality, value) in topic_weights), None)
        if cached is not None:
            result[item["logical_item_id"]] = list(cached)
            continue
        transformed = models[modality].transform(vectorizers[modality].transform([str(item["text"])]))[0]
        normalized = _normalize_topic_vector(transformed)
        if normalized is not None:
            result[item["logical_item_id"]] = normalized
    return result


def _window_for(timestamp: datetime, phase: str, windows: Sequence[Mapping[str, Any]]) -> int | None:
    for window in windows:
        if window["phase"] == phase and window["start"] <= timestamp < window["end"]:
            return int(window["index"])
    return None


def _specialization_observations(
    *,
    items: Sequence[Mapping[str, Any]],
    canonical_rows: Sequence[Mapping[str, Any]],
    topic_vectors: Mapping[str, Sequence[float]],
    structural_windows: Sequence[Mapping[str, Any]],
    action_types: Sequence[str],
    interval: Mapping[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    observations: dict[str, list[dict[str, Any]]] = {"communication": [], "intention": [], "action_type": []}
    for item in items:
        if not item.get("agent_id") or item["logical_item_id"] not in topic_vectors:
            continue
        modality = "communication" if item["source_type"] == "chat" else "intention" if item["source_type"] == "session_goal" else None
        if modality is None or item["phase"] not in {"antecedent", "followup"}:
            continue
        index = _window_for(item["timestamp"], item["phase"], structural_windows)
        if index is not None:
            observations[modality].append(
                {
                    "agent_id": item["agent_id"],
                    "agent_name": item.get("agent_name"),
                    "phase": item["phase"],
                    "window_index": index,
                    "vector": topic_vectors[item["logical_item_id"]],
                }
            )
    action_index = {value: index for index, value in enumerate(action_types)}
    for row in canonical_rows:
        if row["event_kind"] != "high_level_event" or not row.get("agent_id") or row.get("action_type") not in action_index:
            continue
        timestamp = row["event_timestamp"]
        phase = "antecedent" if interval["antecedent_start"] <= timestamp < interval["antecedent_end"] else "followup" if interval["followup_start"] <= timestamp < interval["followup_end"] else None
        if phase is None:
            continue
        index = _window_for(timestamp, phase, structural_windows)
        if index is None:
            continue
        vector = [0.0] * len(action_types)
        vector[action_index[str(row["action_type"])]] = 1.0
        observations["action_type"].append(
            {
                "agent_id": row["agent_id"],
                "agent_name": row.get("agent_name"),
                "phase": phase,
                "window_index": index,
                "vector": vector,
            }
        )
    return observations


def _chronology(
    items: Sequence[Mapping[str, Any]],
    ranked: Sequence[Mapping[str, Any]],
    boundary: datetime,
) -> list[dict[str, Any]]:
    by_id = {item["logical_item_id"]: item for item in items}
    selected: dict[str, dict[str, Any]] = {}

    def add(item: Mapping[str, Any], reason: str) -> None:
        key = str(item["logical_item_id"])
        if key not in selected:
            selected[key] = {
                "logical_item_id": key,
                "timestamp": item["timestamp"],
                "phase": item["phase"],
                "agent_name": item.get("agent_name"),
                "source_type": item["source_type"],
                "action_type": item.get("action_type"),
                "text": item.get("text"),
                "provenance": item["provenance"],
                "selection_reasons": [],
            }
        if reason not in selected[key]["selection_reasons"]:
            selected[key]["selection_reasons"].append(reason)

    for row in ranked:
        add(by_id[row["logical_item_id"]], f"ranked preceding event {row['preceding_event_rank']}")
        for match in row["uptake"]["highest_scoring_matches"][:2]:
            if match["logical_item_id"] in by_id:
                add(by_id[match["logical_item_id"]], f"high-scoring semantic match to preceding event {row['preceding_event_rank']}")
    followup = [item for item in items if item["timestamp"] >= boundary]
    for source_type in ("chat", "user_talk", "session_goal", "high_level_action"):
        for item in [value for value in followup if value["source_type"] == source_type][:2]:
            add(item, f"first {source_type} item after boundary")
    return sorted(selected.values(), key=lambda row: (row["timestamp"], row["logical_item_id"]))


def _null_findings(
    ranked: Sequence[Mapping[str, Any]],
    structure: Mapping[str, Any],
    specialization: Mapping[str, Any],
    context_flags: Sequence[str],
) -> list[str]:
    findings = []
    supported = [row for row in ranked if row["antecedent_support"] in {"moderate", "strong"}]
    if not supported:
        findings.append("No retained preceding evidence reached moderate descriptive antecedent support under the configured observable-evidence rubric.")
    if not any(row["uptake"]["matching_other_agent_count"] for row in ranked):
        findings.append("No convincing multi-agent uptake: no retained preceding event had a qualifying semantic match from another agent.")
    classifications = {row["behavioral_follow_through"]["classification"] for row in ranked}
    if classifications <= {"no_observable_follow_through"}:
        findings.append("No observable behavioral follow-through: qualifying matches were absent or confined to communication.")
    elif "multi_agent_follow_through" not in classifications:
        findings.append("Follow-through was limited to one agent at a time; no retained event had multi-agent behavioral follow-through.")
    if not any(row["uptake"]["matching_item_count"] for row in ranked):
        findings.append("Weak semantic evidence: no later item cleared its recorded source-pair threshold.")
    if not any(row["persistence"]["category"] == "persistent" for row in ranked):
        findings.append("No retained preceding-event pattern persisted across multiple contiguous follow-up windows.")
    recurring = structure["antecedent"]["co_activity"]["recurring_same_window_pair_count"] + structure["followup"]["co_activity"]["recurring_same_window_pair_count"]
    if recurring == 0:
        findings.append("No recurring same-window co-activity pair was observed across the configured subwindows.")
    persistent_specialization = sum(
        row["persistent_specialization"]
        for modality in specialization.values()
        for phase in ("antecedent", "followup")
        for row in modality[phase]["agents"]
    )
    if persistent_specialization == 0:
        findings.append("No agent met the configured repeated-specialization criterion across contiguous windows.")
    stronger = bool(supported or "multi_agent_follow_through" in classifications or persistent_specialization)
    if any(flag in context_flags for flag in ("SESSION_BOUNDARY_NEARBY",)) and not stronger:
        findings.append("The boundary coincides with session-context evidence while stronger continuity evidence is absent; a session-boundary association remains plausible.")
    if not stronger:
        findings.append("No coherent pattern found under the configured preceding-evidence, uptake, follow-through, and specialization rules. Co-activity density alone is not used to avoid this null result.")
    return findings


def run_reconstruction(
    *,
    canonical_path: Path,
    candidates_path: Path,
    candidate_context_path: Path,
    candidate_brief_path: Path,
    inactive_gaps_path: Path,
    stage2_resolved_config_path: Path,
    stage2_cache_dir: Path,
    config: EvidenceReconstructionConfig,
    candidate_ranks: Sequence[int],
    episode_slug: str,
    interim_root: Path,
    output_root: Path,
) -> ReconstructionResult:
    ranks = tuple(sorted(set(int(value) for value in candidate_ranks)))
    if not ranks:
        raise ValueError("at least one candidate rank is required")
    input_identity = {
        "canonical_sha256": _hash_file(canonical_path),
        "candidates_sha256": _hash_file(candidates_path),
        "candidate_context_sha256": _hash_file(candidate_context_path),
        "candidate_brief_sha256": _hash_file(candidate_brief_path),
        "inactive_gaps_sha256": _hash_file(inactive_gaps_path),
        "stage2_resolved_configuration_sha256": _hash_file(stage2_resolved_config_path),
        "stage2_topic_features_sha256": _hash_file(stage2_cache_dir / "topic_features.parquet"),
        "stage2_topic_labels_sha256": _hash_file(stage2_cache_dir / "topic_labels.json"),
        "stage2_communication_vectorizer_sha256": _hash_file(stage2_cache_dir / "communication_vectorizer.joblib"),
        "stage2_communication_nmf_sha256": _hash_file(stage2_cache_dir / "communication_nmf.joblib"),
        "stage2_intention_vectorizer_sha256": _hash_file(stage2_cache_dir / "intention_vectorizer.joblib"),
        "stage2_intention_nmf_sha256": _hash_file(stage2_cache_dir / "intention_nmf.joblib"),
        "stage3_configuration_sha256": config.fingerprint,
        "candidate_ranks": list(ranks),
    }
    rank_key = "r" + "-".join(str(value) for value in ranks)
    cache_dir = Path(interim_root) / episode_slug / "evidence_reconstruction" / f"{config.fingerprint[:12]}-{input_identity['canonical_sha256'][:12]}-{rank_key}"
    cached_result_path = cache_dir / "evidence_reconstruction.json"
    output_dir = Path(output_root) / episode_slug / "turning_points" / "evidence_reconstruction"
    output_json = output_dir / "evidence_reconstruction.json"
    output_markdown = output_dir / "evidence_reconstruction.md"
    if cached_result_path.is_file():
        cached = json.loads(cached_result_path.read_text(encoding="utf-8"))
        if cached.get("metadata", {}).get("input_identity") == input_identity:
            output_dir.mkdir(parents=True, exist_ok=True)
            output_json.write_text(cached_result_path.read_text(encoding="utf-8"), encoding="utf-8")
            output_markdown.write_text(render_markdown(cached), encoding="utf-8", newline="\n")
            return ReconstructionResult(output_json, output_markdown, cache_dir, True, len(cached["candidates"]))

    canonical_rows = pq.read_table(canonical_path).to_pylist()
    all_candidates = pq.read_table(candidates_path).to_pylist()
    candidates_by_rank = {int(row["rank"]): row for row in all_candidates}
    missing = [rank for rank in ranks if rank not in candidates_by_rank]
    if missing:
        raise ValueError(f"candidate ranks not present in frozen Stage 2 output: {missing}")
    context_packet = json.loads(candidate_context_path.read_text(encoding="utf-8"))
    brief_packet = json.loads(candidate_brief_path.read_text(encoding="utf-8"))
    brief_by_rank = {int(row["rank"]): row for row in brief_packet["candidates"]}
    context_by_rank = {int(row["rank"]): row for row in context_packet["candidates"]}
    stage2_resolved = json.loads(stage2_resolved_config_path.read_text(encoding="utf-8"))
    recommended_minutes = int(stage2_resolved["recommended_window_minutes"])
    analysis_minutes = config.windows.analysis_window_minutes or recommended_minutes
    inactive_gaps = _load_inactive_gaps(inactive_gaps_path, recommended_minutes)
    topic_feature_rows = pq.read_table(stage2_cache_dir / "topic_features.parquet").to_pylist()
    topic_weights = {(row["modality"], row["canonical_event_id"]): row["weights"] for row in topic_feature_rows}
    topic_labels = json.loads((stage2_cache_dir / "topic_labels.json").read_text(encoding="utf-8"))
    episode_goal_ids = {row["village_goal_id"] for row in canonical_rows}
    episode_goals = {row["village_goal_text"] for row in canonical_rows}
    episode_starts = {row["village_goal_start"] for row in canonical_rows}
    episode_ends = {row["village_goal_end"] for row in canonical_rows}
    if len(episode_goal_ids) != 1 or len(episode_goals) != 1 or len(episode_starts) != 1 or len(episode_ends) != 1:
        raise ValueError("canonical data must describe exactly one closed episode")
    episode_start = next(iter(episode_starts))
    episode_end = next(iter(episode_ends))
    if episode_end is None:
        raise ValueError("Stage 3 requires a closed episode interval")
    known_agents = {
        str(row["agent_id"]): str(row["agent_name"])
        for row in canonical_rows
        if row.get("agent_id") and row.get("agent_name")
    }
    result: dict[str, Any] = {
        "metadata": {
            "episode_slug": episode_slug,
            "episode_goal_id": next(iter(episode_goal_ids)),
            "episode_goal": next(iter(episode_goals)),
            "episode_interval": {"start": episode_start, "end": episode_end},
            "candidate_ranks": list(ranks),
            "configuration": config.as_dict(),
            "configuration_sha256": config.fingerprint,
            "input_identity": input_identity,
            "semantic_method": "local deterministic word unigram/bigram TF-IDF cosine; fit on baseline+antecedent text only",
            "causal_interpretation": False,
            "social_process_labels": False,
        },
        "candidates": [],
    }
    cache_dir.mkdir(parents=True, exist_ok=True)
    for rank in ranks:
        candidate = candidates_by_rank[rank]
        brief = brief_by_rank[rank]
        boundary = candidate["transition_timestamp"]
        intervals = reconstruction_intervals(
            boundary,
            episode_start=episode_start,
            episode_end=episode_end,
            inactive_gaps=inactive_gaps,
            antecedent_minutes=config.windows.antecedent_minutes,
            followup_minutes=config.windows.followup_minutes,
            baseline_minutes=config.windows.baseline_minutes,
        )
        items = build_logical_items(
            canonical_rows,
            boundary=boundary,
            start=intervals["baseline_start"],
            end=intervals["followup_end"],
            baseline_start=intervals["baseline_start"],
            antecedent_start=intervals["antecedent_start"],
        )
        _write_json(cache_dir / f"logical_items_candidate_{rank}.json", items)
        semantic_space = build_semantic_space(
            items,
            config.semantics,
            model_path=cache_dir / f"candidate_{rank}_semantic_vectorizer.joblib",
        )
        thresholds = semantic_space.thresholds if semantic_space is not None else {
            "common": {"value": config.semantics.fallback_threshold, "pair_count": 0, "method": "no_semantic_space"}
        }
        structural_windows = build_structural_windows(
            canonical_rows,
            antecedent_start=intervals["antecedent_start"],
            boundary=boundary,
            followup_end=intervals["followup_end"],
            minutes=analysis_minutes,
        )
        structure = structural_summary(structural_windows, config=config.structure)
        address_edges = explicit_address_edges(items, known_agents)
        topic_vectors = _topic_vectors_for_items(
            items,
            topic_weights=topic_weights,
            stage2_cache_dir=stage2_cache_dir,
        )
        changes = stage2_distribution_changes(canonical_rows, candidate, topic_weights, topic_labels)
        observations = _specialization_observations(
            items=items,
            canonical_rows=canonical_rows,
            topic_vectors=topic_vectors,
            structural_windows=structural_windows,
            action_types=changes["action_types"],
            interval=intervals,
        )
        eligible_windows = {
            phase: sum(window["active"] for window in structural_windows if window["phase"] == phase)
            for phase in ("antecedent", "followup")
        }
        specialization = {
            "communication": specialization_summary(
                observations["communication"], labels=topic_labels["communication"], eligible_windows_by_phase=eligible_windows, config=config.structure
            ),
            "intention": specialization_summary(
                observations["intention"], labels=topic_labels["intention"], eligible_windows_by_phase=eligible_windows, config=config.structure
            ),
            "action_type": specialization_summary(
                observations["action_type"], labels=changes["action_types"], eligible_windows_by_phase=eligible_windows, config=config.structure
            ),
        }
        followup_windows = [window for window in structural_windows if window["phase"] == "followup" and window["active"]]
        ranked = rank_preceding_events(
            items=items,
            canonical_rows=canonical_rows,
            boundary=boundary,
            antecedent_start=intervals["antecedent_start"],
            followup_end=intervals["followup_end"],
            followup_windows=followup_windows,
            semantic_space=semantic_space,
            topic_vectors_by_item=topic_vectors,
            stage2_changes=changes,
            antecedent_config=config.antecedents,
            antecedent_support_config=config.antecedent_support,
            semantic_config=config.semantics,
            persistence_config=config.persistence,
        )
        context_flags = list(brief["context_flags"])
        context_user_messages = []
        for message in context_by_rank[rank]["external_context"]["user_talk_messages"]:
            message_text = message.get("chat_text") or ""
            automated = (message.get("agent_name") or "").casefold() == "automated" or "automated nudge" in message_text.casefold()
            context_user_messages.append(
                {
                    "type": "automated_nudge" if automated else "user_talk_or_admin_message",
                    "description": message_text,
                    "time_or_date": message["timestamp"],
                    "precision": "timestamp",
                    "provenance": message["canonical_event_id"],
                    "agent_name": message.get("agent_name"),
                }
            )
        external_context_events = context_user_messages + list(brief["external_context_events"])
        external_context_events.sort(key=lambda row: (str(row["time_or_date"]), row["type"], row["provenance"]))
        nulls = _null_findings(ranked, structure, specialization, context_flags)
        caveats = [
            "Semantic similarity is lexical TF-IDF similarity and can miss paraphrases or reward shared boilerplate.",
            "Same-window co-activity is an activity-density/context measure, not relational evidence; same-room overlap also does not demonstrate interaction or influence.",
            "The aggregate-score reference and descriptive antecedent-support rubric were not calibrated on Candidate 2 or Candidate 4 outcomes and do not establish antecedent status.",
            "Stage 2 participation and action-type signals share the same high-level-event stream and are complementary rather than independent.",
        ]
        if any(intervals["truncated_by_inactive_gap"].values()):
            caveats.append("At least one requested reconstruction interval was shortened at an episode boundary or inactive gap; coverage is reported explicitly.")
        if intervals["coverage_minutes"]["baseline"] == 0:
            caveats.append("No gap-free baseline interval was available, so novelty scores are null rather than inferred across inactivity.")
        candidate_result = {
            "rank": rank,
            "comparison_id": candidate["comparison_id"],
            "turning_point_timestamp": boundary,
            "aggregate_score": candidate["aggregate_score"],
            "detector_component_scores": candidate_component_scores(candidate),
            "deterministic_change_description": brief["deterministic_change_description"],
            "windows": intervals,
            "semantic_thresholds": thresholds,
            "provisional_aggregate_score_reference": {
                "threshold": config.antecedents.provisional_score_reference_threshold,
                "establishes_antecedent_status": False,
                "top_n_always_retained": config.antecedents.top_n,
                "above_reference_count": sum(row["above_provisional_score_reference"] for row in ranked),
                "antecedent_support_counts": {
                    level: sum(row["antecedent_support"] == level for row in ranked)
                    for level in ("limited", "moderate", "strong")
                },
            },
            "ranked_preceding_events": ranked,
            "chronological_evidence_sequence": _chronology(items, ranked, boundary),
            "uptake_diffusion_observations": [
                {
                    "preceding_event_rank": row["preceding_event_rank"],
                    "logical_item_id": row["logical_item_id"],
                    "uptake": row["uptake"],
                    "behavioral_follow_through": row["behavioral_follow_through"],
                }
                for row in ranked
            ],
            "distinct_agents_in_reconstruction": {
                "count": len({str(item["agent_id"]) for item in items if item.get("agent_id")}),
                "active_agent_ids": sorted({str(item["agent_id"]) for item in items if item.get("agent_id")}),
                "episode_agent_denominator": len(known_agents),
            },
            "actor_and_structure": structure,
            "explicit_address_relationships": address_edges,
            "role_task_asymmetry": specialization,
            "persistence_observations": [
                {"preceding_event_rank": row["preceding_event_rank"], **row["persistence"]}
                for row in ranked
            ],
            "external_context": {
                "flags": context_flags,
                "events": external_context_events,
                "stage2_5_context_interval": {
                    "start": context_by_rank[rank]["context_start"],
                    "end": context_by_rank[rank]["context_end"],
                },
                "contextual_coincidences_only": True,
            },
            "relationship_to_stage2_signal": {
                "detector_component_scores": candidate_component_scores(candidate),
                "population_alignment_is_not_agent_follow_through": True,
                "description": brief["deterministic_change_description"],
            },
            "null_findings": nulls,
            "caveats": caveats,
            "full_context_reference": f"../candidate_context.md#candidate-{rank}",
        }
        result["candidates"].append(candidate_result)
        _write_json(cache_dir / f"semantic_thresholds_candidate_{rank}.json", thresholds)
        _write_json(cache_dir / f"structural_features_candidate_{rank}.json", {"windows": structural_windows, "summary": structure, "specialization": specialization})

    _write_json(cache_dir / "metadata.json", input_identity)
    _write_json(cached_result_path, result)
    output_dir.mkdir(parents=True, exist_ok=True)
    serialized_text = cached_result_path.read_text(encoding="utf-8")
    serialized_result = json.loads(serialized_text)
    output_json.write_text(serialized_text, encoding="utf-8")
    output_markdown.write_text(render_markdown(serialized_result), encoding="utf-8", newline="\n")
    return ReconstructionResult(output_json, output_markdown, cache_dir, False, len(result["candidates"]))
