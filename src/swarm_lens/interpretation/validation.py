"""Deterministic validation and confidence caps for model proposals."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from .config import InterpretationRules
from .evidence_bundle import evidence_catalog
from .hypotheses import HypothesisLibrary
from .schemas import ModelInterpretation


@dataclass(frozen=True)
class InterpretationValidation:
    valid: bool
    errors: tuple[str, ...]
    validated_interpretation: dict[str, Any] | None


def _all_evidence_references(value: Mapping[str, Any]) -> list[str]:
    references: list[str] = []
    references.extend(value["analyst_note"]["supporting_evidence_ids"])
    for statement in value["interpretive_statements"]:
        references.extend(statement["supporting_evidence_ids"])
    evaluation = value["social_process_evaluation"]
    references.extend(evaluation["supporting_evidence_ids"])
    if evaluation["comparative_rationale"] is not None:
        references.extend(evaluation["comparative_rationale"]["evidence_ids"])
    for hypothesis in evaluation["hypotheses"]:
        for signature in hypothesis["supported_signatures"]:
            references.extend(signature["evidence_ids"])
        for counter in hypothesis["contradicted_counter_signatures"]:
            references.extend(counter["evidence_ids"])
        for alternative in hypothesis["alternative_explanations"]:
            references.extend(alternative["evidence_ids"])
        for group in hypothesis["evidence_groups"]:
            references.extend(group["evidence_ids"])
    return references


def _minimum_confidence(values: Sequence[str], order: tuple[str, ...]) -> str:
    return min(values, key=order.index)


def _evidence_diversity(group_count: int, rules: InterpretationRules) -> str:
    if group_count >= rules.high_evidence_diversity_min_groups:
        return "high"
    if group_count >= rules.moderate_evidence_diversity_min_groups:
        return "moderate"
    return "low"


def validate_interpretation(
    payload: Any,
    *,
    evidence_bundle: Mapping[str, Any],
    library: HypothesisLibrary,
    rules: InterpretationRules,
) -> InterpretationValidation:
    errors: list[str] = []
    try:
        parsed = ModelInterpretation.model_validate(payload).model_dump(mode="json")
    except ValidationError as error:
        return InterpretationValidation(False, tuple(str(error).splitlines()), None)

    catalog = evidence_catalog(evidence_bundle)
    unknown_evidence = sorted(set(_all_evidence_references(parsed)) - set(catalog))
    if unknown_evidence:
        errors.append(f"unknown evidence IDs: {unknown_evidence}")

    evaluation = parsed["social_process_evaluation"]
    hypotheses = evaluation["hypotheses"]
    if evaluation["result"] == "no_clear_social_process_match" and hypotheses:
        errors.append("no_clear_social_process_match requires an empty hypotheses array")
    if evaluation["result"] == "no_clear_social_process_match" and evaluation["comparative_rationale"] is not None:
        errors.append("no_clear_social_process_match requires comparative_rationale=null")
    if evaluation["result"] == "candidate_hypotheses" and not hypotheses:
        errors.append("candidate_hypotheses requires at least one hypothesis")
    if evaluation["result"] == "candidate_hypotheses" and len(hypotheses) > 1 and evaluation["comparative_rationale"] is None:
        errors.append("two or more candidate hypotheses require comparative_rationale")
    if len(hypotheses) > rules.max_hypotheses:
        errors.append(f"at most {rules.max_hypotheses} hypotheses may be returned")
    hypothesis_ids = [value["hypothesis_id"] for value in hypotheses]
    if len(hypothesis_ids) != len(set(hypothesis_ids)):
        errors.append("hypothesis IDs must be unique within a candidate")
    if hypotheses:
        roles = [value["interpretation_role"] for value in hypotheses]
        if roles[0] != "best_supported_candidate":
            errors.append("the first hypothesis must be the best_supported_candidate")
        if roles.count("best_supported_candidate") != 1:
            errors.append("candidate hypotheses require exactly one best_supported_candidate")
        if any(role != "plausible_alternative" for role in roles[1:]):
            errors.append("hypotheses after the first must be plausible_alternative interpretations")
        comparison = evaluation["comparative_rationale"]
        if comparison is not None and comparison["primary_hypothesis_id"] != hypotheses[0]["hypothesis_id"]:
            errors.append("comparative_rationale.primary_hypothesis_id must match the best_supported_candidate")

    library_by_id = library.by_id
    confidence_order = rules.confidence_levels
    capped_hypotheses: list[dict[str, Any]] = []
    for proposed in hypotheses:
        hypothesis_id = proposed["hypothesis_id"]
        if hypothesis_id not in library_by_id:
            errors.append(f"unsupported hypothesis ID: {hypothesis_id!r}")
            continue
        definition = library_by_id[hypothesis_id]
        supported = proposed["supported_signatures"]
        supported_ids = [value["signature_id"] for value in supported]
        if len(supported_ids) != len(set(supported_ids)):
            errors.append(f"{hypothesis_id}: supported signature IDs must be unique")
        unknown_supported = set(supported_ids) - definition.signature_ids
        if unknown_supported:
            errors.append(f"{hypothesis_id}: unsupported signature IDs: {sorted(unknown_supported)}")
        unknown_ids = proposed["unknown_signature_ids"]
        if len(unknown_ids) != len(set(unknown_ids)):
            errors.append(f"{hypothesis_id}: unknown signature IDs must be unique")
        invalid_unknown = set(unknown_ids) - definition.signature_ids
        if invalid_unknown:
            errors.append(f"{hypothesis_id}: invalid unknown signature IDs: {sorted(invalid_unknown)}")
        overlap = set(supported_ids) & set(unknown_ids)
        if overlap:
            errors.append(f"{hypothesis_id}: signatures cannot be both supported and unknown: {sorted(overlap)}")
        unclassified = definition.signature_ids - set(supported_ids) - set(unknown_ids)
        if unclassified:
            errors.append(f"{hypothesis_id}: absent signature evidence must be explicitly unknown: {sorted(unclassified)}")
        if len(supported) < rules.minimum_supported_signatures:
            errors.append(
                f"{hypothesis_id}: needs at least {rules.minimum_supported_signatures} supported signatures, got {len(supported)}"
            )

        substantive_signature_count = 0
        for signature in supported:
            evidence_ids = signature["evidence_ids"]
            known_items = [catalog[value] for value in evidence_ids if value in catalog]
            if not any(item.get("provenance_backed") for item in known_items):
                errors.append(f"{hypothesis_id}/{signature['signature_id']}: supported signature lacks provenance-backed evidence")
            if any(item.get("admissible_for_hypothesis_support") for item in known_items):
                substantive_signature_count += 1
            else:
                errors.append(
                    f"{hypothesis_id}/{signature['signature_id']}: temporal, contextual, or activity-density evidence alone cannot support a signature"
                )
        if substantive_signature_count < rules.minimum_substantive_supported_signatures:
            errors.append(
                f"{hypothesis_id}: needs at least {rules.minimum_substantive_supported_signatures} substantively supported signature(s)"
            )

        groups = proposed["evidence_groups"]
        group_ids = [value["group_id"] for value in groups]
        if len(group_ids) != len(set(group_ids)):
            errors.append(f"{hypothesis_id}: evidence group IDs must be unique")
        grouped_signature_ids: set[str] = set()
        evidence_group_membership: dict[str, str] = {}
        cited_by_signature = {
            signature_id: set(next(value["evidence_ids"] for value in supported if value["signature_id"] == signature_id))
            for signature_id in supported_ids
        }
        for group in groups:
            group_signature_ids = group["supported_signature_ids"]
            if len(group_signature_ids) != len(set(group_signature_ids)):
                errors.append(f"{hypothesis_id}/{group['group_id']}: supported signature IDs must be unique")
            invalid_group_signatures = set(group_signature_ids) - set(supported_ids)
            if invalid_group_signatures:
                errors.append(
                    f"{hypothesis_id}/{group['group_id']}: group refers to unsupported signatures: {sorted(invalid_group_signatures)}"
                )
            grouped_signature_ids.update(group_signature_ids)
            group_evidence_ids = group["evidence_ids"]
            if len(group_evidence_ids) != len(set(group_evidence_ids)):
                errors.append(f"{hypothesis_id}/{group['group_id']}: evidence IDs must be unique")
            allowed_for_group = set().union(
                *(cited_by_signature.get(signature_id, set()) for signature_id in group_signature_ids)
            )
            unrelated = set(group_evidence_ids) - allowed_for_group
            if unrelated:
                errors.append(
                    f"{hypothesis_id}/{group['group_id']}: evidence is not cited by its supported signatures: {sorted(unrelated)}"
                )
            for evidence_id in group_evidence_ids:
                prior = evidence_group_membership.get(evidence_id)
                if prior is not None:
                    errors.append(
                        f"{hypothesis_id}: evidence {evidence_id} cannot count in independent groups {prior!r} and {group['group_id']!r}"
                    )
                evidence_group_membership[evidence_id] = group["group_id"]
            known_group_items = [catalog[value] for value in group_evidence_ids if value in catalog]
            if not any(item.get("provenance_backed") for item in known_group_items):
                errors.append(f"{hypothesis_id}/{group['group_id']}: evidence group lacks provenance-backed evidence")
            if group["relational_evidence"] and not any(
                item.get("relational_evidence") is True for item in known_group_items
            ):
                errors.append(
                    f"{hypothesis_id}/{group['group_id']}: relational_evidence=true lacks a deterministically relational evidence item"
                )
        ungrouped_signatures = set(supported_ids) - grouped_signature_ids
        if ungrouped_signatures:
            errors.append(f"{hypothesis_id}: supported signatures lack an evidence group: {sorted(ungrouped_signatures)}")

        counter_ids = [value["counter_signature_id"] for value in proposed["contradicted_counter_signatures"]]
        if len(counter_ids) != len(set(counter_ids)):
            errors.append(f"{hypothesis_id}: contradicted counter-signature IDs must be unique")
        invalid_counters = set(counter_ids) - definition.counter_signature_ids
        if invalid_counters:
            errors.append(f"{hypothesis_id}: unsupported counter-signature IDs: {sorted(invalid_counters)}")
        for counter in proposed["contradicted_counter_signatures"]:
            known_items = [catalog[value] for value in counter["evidence_ids"] if value in catalog]
            if not any(item.get("provenance_backed") for item in known_items):
                errors.append(f"{hypothesis_id}/{counter['counter_signature_id']}: counter-signature lacks positive provenance-backed evidence")

        cap = "high"
        cap_reasons: list[str] = []
        high_requirements = set(definition.required_signature_ids_for_high_confidence)
        if not high_requirements.issubset(set(supported_ids)):
            cap = _minimum_confidence((cap, "moderate"), confidence_order)
            missing = sorted(high_requirements - set(supported_ids))
            cap_reasons.append(f"missing library high-confidence requirements: {missing}")
        if supported and all(
            not any(catalog.get(evidence_id, {}).get("admissible_for_hypothesis_support") for evidence_id in signature["evidence_ids"])
            for signature in supported
        ):
            cap = _minimum_confidence((cap, definition.context_only_confidence_cap, rules.context_only_confidence_cap), confidence_order)
            cap_reasons.append("support is limited to temporal/context/activity-density evidence")
        counter_by_id = {value.id: value for value in definition.counter_signatures}
        for counter_id in counter_ids:
            if counter_id in counter_by_id:
                counter_cap = counter_by_id[counter_id].confidence_cap
                cap = _minimum_confidence((cap, counter_cap), confidence_order)
                cap_reasons.append(f"counter-signature {counter_id} caps confidence at {counter_cap}")
        displayed = _minimum_confidence((proposed["proposed_confidence"], cap), confidence_order)
        capped = deepcopy(proposed)
        capped["allowed_confidence_cap"] = cap
        capped["displayed_confidence"] = displayed
        capped["confidence_cap_reasons"] = cap_reasons
        capped["supported_signature_count"] = len(supported)
        capped["independent_evidence_group_count"] = len(groups)
        capped["evidence_diversity"] = _evidence_diversity(len(groups), rules)
        correlated = len(groups) < len(supported) or any(len(group["supported_signature_ids"]) > 1 for group in groups)
        capped["correlated_evidence_caveat"] = (
            "Multiple supported signatures depend on at least one shared evidence group and must not be treated as independent confirmations."
            if correlated
            else None
        )
        capped_hypotheses.append(capped)

    if errors:
        return InterpretationValidation(False, tuple(errors), None)
    validated = deepcopy(parsed)
    validated["social_process_evaluation"]["hypotheses"] = capped_hypotheses
    return InterpretationValidation(True, (), validated)
