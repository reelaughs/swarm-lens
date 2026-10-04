"""Build the frozen SwarmLens frontend view model from product artifacts only."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import Counter
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from swarm_lens.interpretation.config import load_config  # noqa: E402
from swarm_lens.interpretation.evidence_bundle import (  # noqa: E402
    canonical_json,
    evidence_catalog,
    hash_json,
)
from swarm_lens.interpretation.hypotheses import load_hypothesis_library  # noqa: E402
from swarm_lens.interpretation.schemas import ModelInterpretation, response_json_schema  # noqa: E402


EPISODE_SLUG = "perform-novel-research"
EPISODE_GOAL = "Perform novel research!"
VIEW_MODEL_VERSION = "1.0"
PRESENTATION_LABEL = "Frozen pipeline"
STAGE4_CACHE_KEYS = {
    1: "6d50d54e63018955ebd93fc1",
    2: "625641230f110578e7d1314b",
    3: "3ebf55addfb880066a3e19c9",
    4: "679a792ad7284b2278aae8a5",
    5: "02e3cf794218704efcfc478c",
}
SIGNALS = (
    ("communication", "Communication"),
    ("intention", "Intention"),
    ("participation", "Participation"),
    ("action_type", "Action type"),
)


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hash_text(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hash_schema() -> str:
    payload = canonical_json(response_json_schema()).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return None if math.isnan(value) else value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "item"):
        return _json_safe(value.item())
    return str(value)


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _same_time(*values: str) -> bool:
    return len({_parse_time(value) for value in values}) == 1


def _collect_evidence_ids(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for item in value.values():
            found.update(_collect_evidence_ids(item))
    elif isinstance(value, list):
        for item in value:
            found.update(_collect_evidence_ids(item))
    elif isinstance(value, str) and value.startswith(("swl-e-", "swl-d-", "swl-c-")):
        found.add(value)
    return found


def _compact_brief_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item["display_key"],
        "timestamp": item["timestamp"],
        "relation": item["relation"],
        "agentName": item.get("agent_name"),
        "agentModel": item.get("agent_model"),
        "eventKind": item.get("event_kind"),
        "actionType": item.get("action_type"),
        "roomId": item.get("room_id"),
        "text": item.get("text"),
        "categories": item.get("categories", []),
        "selectionReasons": item.get("selection_reasons", []),
        "provenance": item.get("provenance", {}),
    }


def _compact_ranked_event(item: dict[str, Any]) -> dict[str, Any]:
    uptake = item.get("uptake", {})
    follow = item.get("behavioral_follow_through", {})
    return {
        "rank": item["preceding_event_rank"],
        "logicalItemId": item["logical_item_id"],
        "timestamp": item["timestamp"],
        "minutesBeforeBoundary": item["minutes_before_boundary"],
        "agentId": item.get("agent_id"),
        "agentName": item.get("agent_name"),
        "sourceType": item.get("source_type"),
        "eventKind": item.get("event_kind"),
        "actionType": item.get("action_type"),
        "roomId": item.get("room_id"),
        "text": item.get("text"),
        "provenance": item.get("provenance", {}),
        "scoreComponents": item.get("score_components", {}),
        "aggregateScore": item.get("aggregate_score"),
        "evidenceLabel": item.get("evidence_label"),
        "antecedentSupport": item.get("antecedent_support"),
        "antecedentSupportDetails": item.get("antecedent_support_details", {}),
        "populationLevelAlignment": item.get("population_level_alignment", {}),
        "uptake": {
            key: value
            for key, value in uptake.items()
            if key != "highest_scoring_matches"
        },
        "behavioralFollowThrough": {
            key: value
            for key, value in follow.items()
            if key not in {"qualifying_semantic_matches", "linked_actions"}
        },
        "persistence": item.get("persistence", {}),
    }


def _component_changes(row: dict[str, Any], key: str) -> Any:
    value = row.get(f"{key}_changes_json")
    if value is None:
        return []
    return json.loads(value) if isinstance(value, str) else value


def _stage4_paths(root: Path, rank: int) -> dict[str, Path]:
    cache_key = STAGE4_CACHE_KEYS[rank]
    base = (
        root
        / "data"
        / "interim"
        / "episodes"
        / EPISODE_SLUG
        / "interpretation"
        / cache_key
        / f"candidate_{rank}"
    )
    return {
        "validated": base / "validated_interpretation.json",
        "bundle": base / "input_evidence_bundle.json",
        "identity": base / "request_identity.json",
    }


def _validate_stage4(
    *,
    root: Path,
    rank: int,
    stage3_hash: str,
    library_fingerprint: str,
    configuration_fingerprint: str,
    schema_hash: str,
    system_prompt_hash: str,
    developer_prompt_hash: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Path]]:
    paths = _stage4_paths(root, rank)
    missing = [str(path) for path in paths.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Candidate {rank} frozen Stage 4 artifact missing: {missing}")
    identity = _read_json(paths["identity"])
    expected = {
        "candidate_rank": rank,
        "stage3_sha256": stage3_hash,
        "configuration_sha256": configuration_fingerprint,
        "hypothesis_library_sha256": library_fingerprint,
        "system_prompt_sha256": system_prompt_hash,
        "developer_prompt_sha256": developer_prompt_hash,
        "response_schema_sha256": schema_hash,
    }
    disagreements = {
        key: {"expected": value, "actual": identity.get(key)}
        for key, value in expected.items()
        if identity.get(key) != value
    }
    if disagreements:
        raise ValueError(f"Candidate {rank} Stage 4 identity mismatch: {disagreements}")
    calculated_key = hashlib.sha256(canonical_json(identity).encode("utf-8")).hexdigest()[:24]
    if calculated_key != STAGE4_CACHE_KEYS[rank]:
        raise ValueError(
            f"Candidate {rank} cache key mismatch: expected {STAGE4_CACHE_KEYS[rank]}, calculated {calculated_key}"
        )

    bundle = _read_json(paths["bundle"])
    if bundle.get("bundle_version") != "2.0":
        raise ValueError(f"Candidate {rank} evidence bundle is not version 2.0")
    embedded_bundle_hash = bundle.get("evidence_bundle_sha256")
    unhashed_bundle = deepcopy(bundle)
    unhashed_bundle.pop("evidence_bundle_sha256", None)
    if hash_json(unhashed_bundle) != embedded_bundle_hash:
        raise ValueError(f"Candidate {rank} evidence bundle fingerprint mismatch")
    if identity.get("evidence_bundle_sha256") != embedded_bundle_hash:
        raise ValueError(f"Candidate {rank} request identity does not match its evidence bundle")

    validated = _read_json(paths["validated"])
    if validated.get("behavioral_change_rank") != rank:
        raise ValueError(f"Candidate {rank} validated interpretation rank mismatch")
    if validated.get("evidence_bundle_sha256") != embedded_bundle_hash:
        raise ValueError(f"Candidate {rank} validated interpretation bundle mismatch")
    interpretation = deepcopy(validated["interpretation"])
    schema_subset = deepcopy(interpretation)
    derived_hypothesis_fields = {
        "allowed_confidence_cap",
        "displayed_confidence",
        "confidence_cap_reasons",
        "supported_signature_count",
        "independent_evidence_group_count",
        "evidence_diversity",
        "correlated_evidence_caveat",
    }
    for hypothesis in schema_subset["social_process_evaluation"]["hypotheses"]:
        for field in derived_hypothesis_fields:
            hypothesis.pop(field, None)
    ModelInterpretation.model_validate(schema_subset)
    if interpretation["schema_version"] != "1.2":
        raise ValueError(f"Candidate {rank} interpretation is not schema 1.2")

    references = sorted(_collect_evidence_ids(interpretation))
    catalog = evidence_catalog(bundle)
    provenance = bundle["evidence_id_to_provenance"]
    missing_records = [value for value in references if value not in catalog]
    missing_provenance = [value for value in references if value not in provenance]
    if missing_records or missing_provenance:
        raise ValueError(
            f"Candidate {rank} incomplete evidence mapping: records={missing_records}, provenance={missing_provenance}"
        )
    referenced = [
        {
            "evidenceId": evidence_id,
            "record": catalog[evidence_id],
            "provenance": provenance[evidence_id],
        }
        for evidence_id in references
    ]
    return validated, interpretation, {"references": referenced}, paths


def build_view_model(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    canonical_path = root / "data" / "processed" / "episodes" / EPISODE_SLUG / "events.parquet"
    stage2_candidates_path = (
        root / "outputs" / "episodes" / EPISODE_SLUG / "turning_points" / "top_candidates.parquet"
    )
    stage2_config_path = (
        root / "outputs" / "episodes" / EPISODE_SLUG / "turning_points" / "resolved_configuration.json"
    )
    brief_path = root / "outputs" / "episodes" / EPISODE_SLUG / "turning_points" / "candidate_brief.json"
    stage3_path = (
        root
        / "outputs"
        / "episodes"
        / EPISODE_SLUG
        / "turning_points"
        / "evidence_reconstruction"
        / "evidence_reconstruction.json"
    )
    library_path = root / "configs" / "social_process_hypotheses.toml"
    interpretation_config_path = root / "configs" / "interpretation.toml"
    system_prompt_path = root / "prompts" / "stage4_system_v1.txt"
    developer_prompt_path = root / "prompts" / "stage4_developer_v1.txt"
    stage4_schema_path = root / "schemas" / "stage4_interpretation.schema.json"
    required = (
        canonical_path,
        stage2_candidates_path,
        stage2_config_path,
        brief_path,
        stage3_path,
        library_path,
        interpretation_config_path,
        system_prompt_path,
        developer_prompt_path,
        stage4_schema_path,
    )
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing frozen product artifact(s): {missing}")

    stage2_config = _read_json(stage2_config_path)
    brief = _read_json(brief_path)
    stage3 = _read_json(stage3_path)
    library = load_hypothesis_library(library_path)
    interpretation_config = load_config(interpretation_config_path)
    library_names = {item.id: item.name for item in library.hypotheses}
    stage3_hash = _sha256(stage3_path)
    schema_hash = _hash_schema()
    if canonical_json(_read_json(stage4_schema_path)) != canonical_json(response_json_schema()):
        raise ValueError("Checked-in Stage 4 schema does not match the Pydantic response schema")

    event_rows = pq.read_table(
        canonical_path,
        columns=[
            "event_timestamp",
            "event_kind",
            "agent_id",
            "village_goal_id",
            "village_goal_text",
            "village_goal_start",
            "village_goal_end",
        ],
    ).to_pylist()
    if not event_rows:
        raise ValueError("Canonical episode contains no events")
    episode_identity = {
        (
            row["village_goal_id"],
            row["village_goal_text"],
            row["village_goal_start"],
            row["village_goal_end"],
        )
        for row in event_rows
    }
    if len(episode_identity) != 1:
        raise ValueError("Canonical rows do not share one authoritative village-goal identity")
    goal_id, goal_text, goal_start, goal_end = next(iter(episode_identity))
    if goal_text != EPISODE_GOAL:
        raise ValueError(f"Wrong episode: {goal_text!r}")

    stage2_rows = sorted(
        pq.read_table(stage2_candidates_path).to_pylist(), key=lambda value: int(value["rank"])
    )
    brief_by_rank = {int(item["rank"]): item for item in brief["candidates"]}
    stage3_by_rank = {int(item["rank"]): item for item in stage3["candidates"]}
    expected_ranks = list(STAGE4_CACHE_KEYS)
    if [int(item["rank"]) for item in stage2_rows] != expected_ranks:
        raise ValueError("Stage 2 candidates are not frozen ranks 1-5")
    if sorted(brief_by_rank) != expected_ranks or sorted(stage3_by_rank) != expected_ranks:
        raise ValueError("Stage 2.5 or Stage 3 is missing a frozen rank")

    source_identity = {
        "canonicalEvents": {"path": _relative(canonical_path, root), "sha256": _sha256(canonical_path)},
        "stage2Candidates": {
            "path": _relative(stage2_candidates_path, root),
            "sha256": _sha256(stage2_candidates_path),
        },
        "stage2Configuration": {
            "path": _relative(stage2_config_path, root),
            "sha256": _sha256(stage2_config_path),
            "configurationSha256": stage2_config["configuration_sha256"],
        },
        "stage2_5Brief": {"path": _relative(brief_path, root), "sha256": _sha256(brief_path)},
        "stage3Reconstruction": {"path": _relative(stage3_path, root), "sha256": stage3_hash},
        "stage4Configuration": {
            "path": _relative(interpretation_config_path, root),
            "fingerprint": interpretation_config.fingerprint,
        },
        "stage4Schema": {"path": _relative(stage4_schema_path, root), "fingerprint": schema_hash},
        "hypothesisLibrary": {
            "path": _relative(library_path, root),
            "fingerprint": library.fingerprint,
            "version": library.library_version,
            "status": library.library_status,
        },
        "systemPrompt": {"path": _relative(system_prompt_path, root), "sha256": _hash_text(system_prompt_path)},
        "developerPrompt": {
            "path": _relative(developer_prompt_path, root),
            "sha256": _hash_text(developer_prompt_path),
        },
        "stage4CacheManifest": {str(rank): value for rank, value in STAGE4_CACHE_KEYS.items()},
    }

    start_seconds = goal_start.timestamp()
    duration_seconds = goal_end.timestamp() - start_seconds
    candidates = []
    for stage2_row in stage2_rows:
        rank = int(stage2_row["rank"])
        brief_candidate = brief_by_rank[rank]
        stage3_candidate = stage3_by_rank[rank]
        validated, interpretation, stage4_evidence, stage4_paths = _validate_stage4(
            root=root,
            rank=rank,
            stage3_hash=stage3_hash,
            library_fingerprint=library.fingerprint,
            configuration_fingerprint=interpretation_config.fingerprint,
            schema_hash=schema_hash,
            system_prompt_hash=_hash_text(system_prompt_path),
            developer_prompt_hash=_hash_text(developer_prompt_path),
        )
        comparison_ids = {
            stage2_row["comparison_id"],
            brief_candidate["comparison_id"],
            stage3_candidate["comparison_id"],
            validated["comparison_id"],
        }
        if len(comparison_ids) != 1:
            raise ValueError(f"Candidate {rank} comparison identity disagreement: {comparison_ids}")
        if not _same_time(
            stage2_row["transition_timestamp"].isoformat(),
            brief_candidate["turning_point_timestamp"],
            stage3_candidate["turning_point_timestamp"],
            validated["turning_point_timestamp"],
        ):
            raise ValueError(f"Candidate {rank} timestamp disagreement")
        if not math.isclose(
            float(stage2_row["aggregate_score"]),
            float(validated["stage2_aggregate_score"]),
            rel_tol=0,
            abs_tol=1e-12,
        ):
            raise ValueError(f"Candidate {rank} aggregate-score disagreement")

        signals = []
        for signal_id, label in SIGNALS:
            signals.append(
                {
                    "id": signal_id,
                    "label": label,
                    "eligible": bool(stage2_row[f"{signal_id}_eligible"]),
                    "jensenShannonDivergence": _json_safe(stage2_row[f"{signal_id}_js"]),
                    "standardizedScore": _json_safe(stage2_row[f"{signal_id}_z"]),
                    "distributionChanges": _json_safe(_component_changes(stage2_row, signal_id)),
                }
            )

        social = deepcopy(interpretation["social_process_evaluation"])
        for hypothesis in social["hypotheses"]:
            hypothesis_id = hypothesis["hypothesis_id"]
            if hypothesis_id not in library_names:
                raise ValueError(f"Candidate {rank} unknown hypothesis ID: {hypothesis_id}")
            hypothesis["display_name"] = library_names[hypothesis_id]

        transition_time = stage2_row["transition_timestamp"]
        candidates.append(
            {
                "rank": rank,
                "comparisonId": stage2_row["comparison_id"],
                "timestamp": transition_time.isoformat(),
                "timelinePositionPercent": round(
                    100 * (transition_time.timestamp() - start_seconds) / duration_seconds, 6
                ),
                "aggregateDetectorScore": float(stage2_row["aggregate_score"]),
                "contributingComponents": list(stage2_row["contributing_components"]),
                "windowSizeReliable": bool(stage2_row["window_size_reliable"]),
                "signals": signals,
                "deterministicDescriptions": list(
                    brief_candidate.get("deterministic_change_description", [])
                ),
                "activity": {
                    "windowSizeMinutes": int(stage2_row["window_size_minutes"]),
                    "before": {
                        "start": stage2_row["before_window_start"].isoformat(),
                        "end": stage2_row["before_window_end"].isoformat(),
                        "eventCount": int(stage2_row["before_event_count"]),
                        "chatCount": int(stage2_row["before_agent_chat_count"]),
                        "sessionCount": int(stage2_row["before_session_count"]),
                        "highLevelEventCount": int(stage2_row["before_agent_event_count"]),
                        "distinctAgents": int(stage2_row["before_distinct_agents"]),
                    },
                    "after": {
                        "start": stage2_row["after_window_start"].isoformat(),
                        "end": stage2_row["after_window_end"].isoformat(),
                        "eventCount": int(stage2_row["after_event_count"]),
                        "chatCount": int(stage2_row["after_agent_chat_count"]),
                        "sessionCount": int(stage2_row["after_session_count"]),
                        "highLevelEventCount": int(stage2_row["after_agent_event_count"]),
                        "distinctAgents": int(stage2_row["after_distinct_agents"]),
                    },
                },
                "contextFlags": brief_candidate.get("context_flags", []),
                "externalContextEvents": brief_candidate.get("external_context_events", []),
                "compactEvidence": [
                    _compact_brief_item(item)
                    for item in sorted(
                        brief_candidate.get("evidence_items", []), key=lambda value: value["timestamp"]
                    )
                ],
                "reconstruction": {
                    "windows": stage3_candidate.get("windows", {}),
                    "rankedPrecedingEvidence": [
                        _compact_ranked_event(item)
                        for item in stage3_candidate.get("ranked_preceding_events", [])
                    ],
                    "persistenceObservations": stage3_candidate.get("persistence_observations", []),
                    "structuralObservations": {
                        "distinctAgents": stage3_candidate.get("distinct_agents_in_reconstruction", []),
                        "actorAndStructure": stage3_candidate.get("actor_and_structure", {}),
                        "explicitAddressRelationships": stage3_candidate.get(
                            "explicit_address_relationships", {}
                        ),
                        "roleTaskAsymmetry": stage3_candidate.get("role_task_asymmetry", {}),
                        "relationshipToStage2Signal": stage3_candidate.get(
                            "relationship_to_stage2_signal", {}
                        ),
                    },
                    "nullFindings": stage3_candidate.get("null_findings", []),
                    "caveats": stage3_candidate.get("caveats", []),
                },
                "interpretation": {
                    "status": validated.get("interpretation_status"),
                    "schemaVersion": interpretation["schema_version"],
                    "analystNote": interpretation["analyst_note"],
                    "interpretiveStatements": interpretation["interpretive_statements"],
                    "socialProcessEvaluation": social,
                },
                "referencedEvidence": stage4_evidence["references"],
                "sourcePaths": {
                    "stage2": _relative(stage2_candidates_path, root),
                    "stage2_5": _relative(brief_path, root),
                    "stage3": _relative(stage3_path, root),
                    "stage4Validated": _relative(stage4_paths["validated"], root),
                    "stage4EvidenceBundle": _relative(stage4_paths["bundle"], root),
                    "stage4RequestIdentity": _relative(stage4_paths["identity"], root),
                },
            }
        )

    counts = Counter(str(row["event_kind"]) for row in event_rows)
    view_model = {
        "viewModelVersion": VIEW_MODEL_VERSION,
        "presentation": {
            "label": PRESENTATION_LABEL,
            "scope": "Frozen Perform novel research! episode; five Stage 2 behavioral-change candidates.",
            "methodologicalGuardrails": [
                "Behavioral-change rank is not importance rank.",
                "Detector transition magnitude is not interpretation confidence.",
                "Analyst interpretation is not a causal explanation.",
                "A possible social process is not a cause.",
                "Evidence diversity is separate from confidence.",
                "Missing evidence is unknown, not contradiction.",
                "Frozen Stage 2 ordering is preserved; no LLM reranking is performed.",
            ],
        },
        "episode": {
            "slug": EPISODE_SLUG,
            "goalId": goal_id,
            "goalText": goal_text,
            "start": goal_start.isoformat(),
            "end": goal_end.isoformat(),
            "recordCount": len(event_rows),
            "recordCountsByKind": dict(sorted(counts.items())),
            "uniqueAgentCount": len(
                {row["agent_id"] for row in event_rows if row["agent_id"] is not None}
            ),
            "turningPointCount": len(candidates),
        },
        "signalFamilies": [
            {"id": signal_id, "label": label} for signal_id, label in SIGNALS
        ],
        "turningPoints": candidates,
        "sourceIdentity": source_identity,
    }
    validate_view_model(view_model)
    return _json_safe(view_model)


def validate_view_model(value: dict[str, Any]) -> None:
    if value.get("viewModelVersion") != VIEW_MODEL_VERSION:
        raise ValueError("Unexpected frontend view-model version")
    if value["episode"]["goalText"] != EPISODE_GOAL:
        raise ValueError("Unexpected frontend episode")
    ranks = [candidate["rank"] for candidate in value["turningPoints"]]
    if ranks != list(STAGE4_CACHE_KEYS):
        raise ValueError(f"Frontend candidates are not in frozen Stage 2 order: {ranks}")
    for candidate in value["turningPoints"]:
        if not candidate["deterministicDescriptions"]:
            raise ValueError(f"Candidate {candidate['rank']} lacks Stage 2.5 descriptions")
        evaluation = candidate["interpretation"]["socialProcessEvaluation"]
        hypotheses = evaluation["hypotheses"]
        if hypotheses:
            primary = [
                item for item in hypotheses if item["interpretation_role"] == "best_supported_candidate"
            ]
            if len(primary) != 1:
                raise ValueError(f"Candidate {candidate['rank']} must have one primary hypothesis")
        reference_ids = [item["evidenceId"] for item in candidate["referencedEvidence"]]
        cited = sorted(_collect_evidence_ids(candidate["interpretation"]))
        if reference_ids != cited:
            raise ValueError(f"Candidate {candidate['rank']} evidence catalog is incomplete")


def write_view_model(root: Path, output_path: Path) -> dict[str, Any]:
    value = build_view_model(root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "frontend" / "public" / "data" / f"{EPISODE_SLUG}.json",
    )
    args = parser.parse_args()
    write_view_model(args.root.resolve(), args.output.resolve())
    print(f"Validated and wrote {_relative(args.output.resolve(), args.root.resolve())}")


if __name__ == "__main__":
    main()
