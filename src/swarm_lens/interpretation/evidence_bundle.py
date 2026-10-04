"""Build compact, deterministic Stage 4 evidence bundles from Stage 2/3 outputs."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from .config import EvidenceConfig
from .hypotheses import HypothesisLibrary


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def hash_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _clip(value: Any, limit: int) -> Any:
    if value is None:
        return None
    text = str(value)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _provenance_ids(item: Mapping[str, Any]) -> list[str]:
    return sorted(
        {
            str(row["canonical_event_id"])
            for row in item.get("provenance", [])
            if isinstance(row, Mapping) and row.get("canonical_event_id")
        }
    )


def _linked_action_as_record(item: Mapping[str, Any]) -> dict[str, Any]:
    provenance_ids = _provenance_ids(item)
    return {
        "logical_item_id": provenance_ids[0] if provenance_ids else "",
        "timestamp": item.get("timestamp"),
        "phase": "followup",
        "agent_id": item.get("agent_id"),
        "agent_name": item.get("agent_name"),
        "source_type": "high_level_action",
        "event_kind": "high_level_event",
        "action_type": item.get("action_type"),
        "room_id": item.get("room_id"),
        "computer_use_session_id": item.get("computer_use_session_id"),
        "text": item.get("text"),
        "provenance": item.get("provenance", []),
    }


def _raw_candidates(candidate: Mapping[str, Any], config: EvidenceConfig) -> tuple[list[dict[str, Any]], set[str]]:
    """Collect representative logical records and deterministic relational flags."""

    by_logical_id: dict[str, dict[str, Any]] = {}
    explicit_address_ids = {
        str(edge.get("logical_item_id"))
        for edge in candidate.get("explicit_address_relationships", {}).get("edges", [])
        if edge.get("logical_item_id")
    }

    def add(item: Mapping[str, Any], selection_basis: str, priority: int) -> None:
        logical_id = str(item.get("logical_item_id") or "")
        if not logical_id:
            return
        existing = by_logical_id.get(logical_id)
        if existing is None:
            existing = {
                "logical_item_id": logical_id,
                "timestamp": item.get("timestamp"),
                "phase": item.get("phase"),
                "agent_id": item.get("agent_id"),
                "agent_name": item.get("agent_name"),
                "source_type": item.get("source_type"),
                "event_kind": item.get("event_kind"),
                "action_type": item.get("action_type"),
                "room_id": item.get("room_id"),
                "computer_use_session_id": item.get("computer_use_session_id"),
                "text": item.get("text"),
                "provenance": list(item.get("provenance", [])),
                "selection_basis": [],
                "priority": priority,
            }
            by_logical_id[logical_id] = existing
        existing["priority"] = min(int(existing["priority"]), priority)
        if selection_basis not in existing["selection_basis"]:
            existing["selection_basis"].append(selection_basis)
        if not existing.get("text") and item.get("text"):
            existing["text"] = item["text"]
        known = {row.get("canonical_event_id") for row in existing["provenance"] if isinstance(row, Mapping)}
        for row in item.get("provenance", []):
            if isinstance(row, Mapping) and row.get("canonical_event_id") not in known:
                existing["provenance"].append(dict(row))
                known.add(row.get("canonical_event_id"))

    for event in candidate.get("ranked_preceding_events", []):
        rank = event.get("preceding_event_rank")
        add(event, f"ranked preceding evidence {rank}", 0)
        for match in event.get("uptake", {}).get("highest_scoring_matches", [])[: config.max_semantic_examples_per_preceding_event]:
            add(match, f"representative semantic match to preceding evidence {rank}", 1)
        for action in event.get("behavioral_follow_through", {}).get("linked_actions", [])[: config.max_linked_action_examples_per_preceding_event]:
            add(_linked_action_as_record(action), f"representative linked action for preceding evidence {rank}", 1)
    for edge in candidate.get("explicit_address_relationships", {}).get("edges", [])[:10]:
        add(edge, "representative explicit-address record", 1)
    for item in candidate.get("chronological_evidence_sequence", []):
        reasons = item.get("selection_reasons", [])
        add(item, "; ".join(str(value) for value in reasons) or "chronological evidence sequence", 2)
    rows = sorted(
        by_logical_id.values(),
        key=lambda row: (int(row["priority"]), str(row.get("timestamp") or ""), row["logical_item_id"]),
    )
    return rows[: config.max_raw_items], explicit_address_ids


def _library_for_prompt(library: HypothesisLibrary) -> dict[str, Any]:
    return {
        "library_version": library.library_version,
        "library_status": library.library_status,
        "hypotheses": [
            {
                "id": hypothesis.id,
                "name": hypothesis.name,
                "description": hypothesis.description,
                "required_signature_ids_for_high_confidence": list(hypothesis.required_signature_ids_for_high_confidence),
                "signatures": [vars(value) for value in hypothesis.signatures],
                "counter_signatures": [vars(value) for value in hypothesis.counter_signatures],
                "cautions": list(hypothesis.cautions),
            }
            for hypothesis in library.hypotheses
        ],
    }


def _selected(value: Mapping[str, Any], keys: Sequence[str]) -> dict[str, Any]:
    return {key: value.get(key) for key in keys if key in value}


def _scalar_summary(value: Mapping[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if item is None or isinstance(item, (str, int, float, bool))}


def _role_agent_summary(value: Mapping[str, Any]) -> dict[str, Any]:
    return _selected(
        value,
        (
            "agent_id", "agent_name", "observation_count", "qualified_window_count",
            "dominant_component", "dominant_action_type", "dominant_label", "dominant_share",
            "specialization_index", "persistent_specialization", "max_consecutive_qualified_windows",
        ),
    )


def build_evidence_bundle(
    candidate: Mapping[str, Any],
    *,
    episode_metadata: Mapping[str, Any],
    library: HypothesisLibrary,
    config: EvidenceConfig,
) -> dict[str, Any]:
    """Assign stable swl-e/d/c IDs and normalize complete provenance once."""

    raw_rows, explicit_address_ids = _raw_candidates(candidate, config)
    raw_items: list[dict[str, Any]] = []
    raw_id_by_logical: dict[str, str] = {}
    provenance_catalog: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(raw_rows, 1):
        evidence_id = f"swl-e-{index:04d}"
        logical_id = row["logical_item_id"]
        raw_id_by_logical[logical_id] = evidence_id
        provenance = [dict(value) for value in row.get("provenance", []) if isinstance(value, Mapping)]
        relational = True if logical_id in explicit_address_ids else None
        raw_items.append(
            {
                "evidence_id": evidence_id,
                "evidence_kind": "provenance_backed_raw_record",
                "support_role": "explicit_relational_record" if relational else "substantive_record_content",
                "admissible_for_hypothesis_support": bool(provenance),
                "provenance_backed": bool(provenance),
                "relational_evidence": relational,
                "timestamp": row.get("timestamp"), "phase": row.get("phase"),
                "agent_id": row.get("agent_id"), "agent_name": row.get("agent_name"),
                "source_type": row.get("source_type"), "event_kind": row.get("event_kind"),
                "action_type": row.get("action_type"), "room_id": row.get("room_id"),
                "computer_use_session_id": row.get("computer_use_session_id"),
                "text": _clip(row.get("text"), config.max_text_characters_per_item),
                "selection_basis": row["selection_basis"], "provenance_ref": evidence_id,
            }
        )
        provenance_catalog[evidence_id] = {
            "logical_item_id": logical_id,
            "canonical_source_ids": _provenance_ids(row),
            "source_records": provenance,
        }

    derived_items: list[dict[str, Any]] = []

    def add_derived(
        observation_type: str,
        description: str,
        measurement: Any,
        *,
        stage3_path: str,
        source_ids: Sequence[str] = (),
        support_role: str = "deterministic_context",
        admissible: bool = False,
        relational: bool = False,
        evidence_group_key: str | None = None,
    ) -> None:
        if len(derived_items) >= config.max_deterministic_items:
            return
        evidence_id = f"swl-d-{len(derived_items) + 1:04d}"
        references = tuple(sorted(set(source_ids)))
        item = {
            "evidence_id": evidence_id,
            "evidence_kind": "deterministic_stage2_stage3_observation",
            "observation_type": observation_type,
            "description": description,
            "measurement": measurement,
            "supporting_evidence_ids": list(references),
            "support_role": support_role,
            "admissible_for_hypothesis_support": admissible,
            "provenance_backed": bool(references) if admissible else True,
            "relational_evidence": relational,
            "provenance_ref": evidence_id,
        }
        if evidence_group_key:
            item["deterministic_evidence_group_key"] = evidence_group_key
        derived_items.append(item)
        provenance_catalog[evidence_id] = {
            "stage3_source_path": stage3_path,
            "supporting_evidence_ids": list(references),
        }

    add_derived(
        "frozen_detector_reference",
        "Frozen Stage 2 identity and score; temporal detector context, not a social-process finding.",
        {"behavioral_change_rank": candidate["rank"], "comparison_id": candidate["comparison_id"],
         "turning_point_timestamp": candidate["turning_point_timestamp"], "aggregate_score": candidate["aggregate_score"]},
        stage3_path="$candidate", support_role="temporal_detector_context",
    )
    component_keys = ("raw_divergence", "standardized_divergence", "standardized_score", "eligible",
                      "before_count", "after_count", "largest_changes", "top_changes")
    for component, values in candidate.get("detector_component_scores", {}).items():
        compact = _selected(values, component_keys) if isinstance(values, Mapping) else values
        add_derived("detector_component", f"Frozen Stage 2 {component} divergence and largest changes.", compact,
                    stage3_path=f"detector_component_scores.{component}", support_role="population_detector_context")
    windows = candidate.get("windows", {})
    add_derived(
        "reconstruction_coverage", "Stage 3 reconstruction interval and effective coverage.",
        {key: value for key, value in windows.items() if key not in {"window_records", "records", "items"}},
        stage3_path="windows", support_role="observation_coverage_context",
    )
    for event_index, event in enumerate(candidate.get("ranked_preceding_events", [])):
        logical_id = str(event.get("logical_item_id") or "")
        preceding_id = raw_id_by_logical.get(logical_id)
        match_ids = [raw_id_by_logical[value] for match in event.get("uptake", {}).get("highest_scoring_matches", [])
                     if (value := str(match.get("logical_item_id"))) in raw_id_by_logical]
        action_ids = [raw_id_by_logical[value] for action in event.get("behavioral_follow_through", {}).get("linked_actions", [])
                      if (value := (_provenance_ids(action) or [""])[0]) in raw_id_by_logical]
        source_ids = [value for value in [preceding_id, *match_ids, *action_ids] if value]
        uptake = event.get("uptake", {})
        follow = event.get("behavioral_follow_through", {})
        persistence = event.get("persistence", {})
        measurement = {
            "preceding_event_rank": event.get("preceding_event_rank"), "evidence_label": event.get("evidence_label"),
            "antecedent_support": event.get("antecedent_support"),
            "provisional_aggregate_score": event.get("aggregate_score"), "score_components": event.get("score_components"),
            "semantic_uptake": _selected(uptake, ("classification", "matching_item_count", "matching_other_agent_count",
                                                         "matching_agents_over_active_agents", "retained_match_count")),
            "behavioral_follow_through": _selected(follow, ("classification", "semantic_uptake_agent_count",
                "qualifying_follow_through_agent_count", "follow_through_agents_over_semantic_uptake_agents",
                "other_agent_follow_through_count", "linked_action_count", "rule")),
            "persistence": _selected(persistence, ("presence_windows", "eligible_windows", "persistence_ratio",
                                                   "max_consecutive_windows", "category")),
            "population_level_alignment": event.get("population_level_alignment"),
            "correlation_caveat": "Uptake, persistence, and follow-through measurements may arise from one underlying evidence pattern and are not independent confirmations.",
        }
        add_derived(
            "ranked_preceding_evidence_measurement",
            "Compact Stage 3 uptake, follow-through, persistence, alignment, and descriptive support for one preceding record.",
            measurement, stage3_path=f"ranked_preceding_events[{event_index}]", source_ids=source_ids,
            support_role="semantic_uptake_follow_through_measurement",
            admissible=bool(source_ids and (uptake.get("matching_other_agent_count") or follow.get("qualifying_follow_through_agent_count"))),
            relational=False, evidence_group_key=f"preceding_record:{logical_id}:uptake_followthrough",
        )
    structure = candidate.get("actor_and_structure", {})
    for phase in ("antecedent", "followup"):
        phase_value = structure.get(phase, {})
        concentration = phase_value.get("concentration", {})
        add_derived(
            "population_structure", f"Population concentration summary for the {phase} interval.",
            {"phase": phase, "window_count": phase_value.get("window_count"),
             "active_window_count": phase_value.get("active_window_count"),
             "concentration": _scalar_summary(concentration) if isinstance(concentration, Mapping) else concentration},
            stage3_path=f"actor_and_structure.{phase}", support_role="population_structure_context",
        )
        coactivity = phase_value.get("co_activity", {})
        add_derived(
            "same_window_coactivity", f"Same-window co-activity summary for the {phase} interval; activity-density context only.",
            {"phase": phase, **(_scalar_summary(coactivity) if isinstance(coactivity, Mapping) else {})},
            stage3_path=f"actor_and_structure.{phase}.co_activity", support_role="activity_density_context",
            admissible=False, relational=False,
        )
    addresses = candidate.get("explicit_address_relationships", {})
    address_source_ids = [raw_id_by_logical[value] for value in explicit_address_ids if value in raw_id_by_logical]
    edge_pairs = sorted({
        (str(edge.get("source_agent_name") or edge.get("source_agent_id") or ""),
         str(edge.get("target_agent_name") or edge.get("target_agent_id") or ""))
        for edge in addresses.get("edges", [])
    })
    add_derived(
        "explicit_address_relationships", "Explicit-address summary; addressing is relational evidence but does not establish influence.",
        {"explicit_address_edge_count": addresses.get("explicit_address_edge_count", 0),
         "distinct_address_pair_count": len(edge_pairs), "representative_address_pairs": edge_pairs[:5]},
        stage3_path="explicit_address_relationships", source_ids=address_source_ids,
        support_role="explicit_relational_indicator", admissible=bool(address_source_ids), relational=bool(address_source_ids),
    )
    for modality, phases in candidate.get("role_task_asymmetry", {}).items():
        for phase in ("antecedent", "followup"):
            phase_value = phases.get(phase, {})
            qualifying = [value for value in phase_value.get("agents", [])
                          if value.get("qualified") or value.get("persistent_specialization")]
            qualifying.sort(key=lambda value: (not bool(value.get("persistent_specialization")),
                                                -float(value.get("specialization_index") or 0),
                                                str(value.get("agent_id") or "")))
            summaries = [_role_agent_summary(value) for value in qualifying[: config.max_role_agents_per_phase]]
            add_derived(
                "role_task_asymmetry", f"Compact {modality} specialization summary for the {phase} interval.",
                {"modality": modality, "phase": phase, "agent_count_observed": phase_value.get("agent_count_observed"),
                 "agent_count_qualified": phase_value.get("agent_count_qualified"),
                 "mean_pairwise_js_divergence": phase_value.get("mean_pairwise_js_divergence"),
                 "most_relevant_agent_summaries": summaries},
                stage3_path=f"role_task_asymmetry.{modality}.{phase}",
                support_role="repeated_specialization_measurement", admissible=bool(summaries), relational=False,
            )
    for index, finding in enumerate(candidate.get("null_findings", [])):
        add_derived("null_finding", str(finding), {"finding": finding}, stage3_path=f"null_findings[{index}]",
                    support_role="negative_or_missing_evidence_diagnostic")
    for index, caveat in enumerate(candidate.get("caveats", [])):
        add_derived("methodological_caveat", str(caveat), {"caveat": caveat}, stage3_path=f"caveats[{index}]",
                    support_role="methodological_constraint")

    context_items: list[dict[str, Any]] = []
    for index, event in enumerate(candidate.get("external_context", {}).get("events", [])[: config.max_context_items], 1):
        evidence_id = f"swl-c-{index:04d}"
        context_items.append({
            "evidence_id": evidence_id, "evidence_kind": "contextual_observation", "context_type": event.get("type"),
            "description": _clip(event.get("description"), config.max_text_characters_per_item),
            "time_or_date": event.get("time_or_date"), "precision": event.get("precision"),
            "support_role": "contextual_coincidence_only", "admissible_for_hypothesis_support": False,
            "provenance_backed": bool(event.get("provenance")), "relational_evidence": False,
            "provenance_ref": evidence_id,
        })
        provenance_catalog[evidence_id] = {"source_reference": event.get("provenance")}

    bundle = {
        "bundle_version": "2.0",
        "candidate_reference": {
            "episode_slug": episode_metadata["episode_slug"], "episode_goal": episode_metadata["episode_goal"],
            "behavioral_change_rank": candidate["rank"], "comparison_id": candidate["comparison_id"],
            "turning_point_timestamp": candidate["turning_point_timestamp"], "rank_is_frozen_and_not_model_editable": True,
        },
        "interpretation_constraints": {
            "deterministic_observations_authored_by_model": False, "causal_attribution_requested": False,
            "missing_evidence_default": "unknown", "coactivity_evidence_role": "activity_density_context",
            "coactivity_relational_evidence": False, "external_context_is_coincidental_only": True,
            "signature_count_is_not_independent_corroboration": True, "evidence_group_count_is_not_a_display_gate": True,
        },
        "deterministic_observations": {
            "raw_record_evidence": raw_items, "derived_measurements": derived_items,
            "contextual_observations": context_items,
        },
        "evidence_id_to_provenance": provenance_catalog,
        "hypothesis_library": _library_for_prompt(library),
    }
    bundle["evidence_bundle_sha256"] = hash_json(bundle)
    return bundle


def evidence_catalog(bundle: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    observations = bundle["deterministic_observations"]
    items = [*observations["raw_record_evidence"], *observations["derived_measurements"],
             *observations["contextual_observations"]]
    catalog = {str(value["evidence_id"]): value for value in items}
    if len(catalog) != len(items):
        raise ValueError("evidence bundle contains duplicate evidence IDs")
    provenance = bundle.get("evidence_id_to_provenance", {})
    if provenance and set(provenance) != set(catalog):
        raise ValueError("provenance catalog IDs must exactly match evidence IDs")
    return catalog
