"""Human-readable rendering of validated Stage 4 interpretations."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _ids(values: list[str]) -> str:
    return ", ".join(f"`{value}`" for value in values) or "none"


def render_markdown(result: Mapping[str, Any]) -> str:
    metadata = result["metadata"]
    lines = [
        f"# Constrained interpretation: {metadata['episode_goal']}",
        "",
        "Stage 4 interprets deterministic Stage 2/3 evidence. Behavioral-change ranking is inherited and immutable; this report adds no importance score or causal attribution.",
        "",
        f"- Hypothesis library: `{metadata['hypothesis_library_version']}` — {metadata['hypothesis_library_status']}",
        f"- Requested provider/model: `{metadata['provider']}` / `{metadata['requested_model']}`",
        f"- Candidate ranks: `{', '.join(str(value) for value in metadata['candidate_ranks'])}`",
        "",
    ]
    for candidate in result["candidates"]:
        lines.extend(
            [
                f"## Candidate {candidate['behavioral_change_rank']}: {candidate['turning_point_timestamp']}",
                "",
                f"- Status: `{candidate['interpretation_status']}`",
                f"- Frozen comparison: `{candidate['comparison_id']}`",
                f"- Stage 2 aggregate score: `{candidate['stage2_aggregate_score']:.3f}`",
                f"- Evidence bundle: `{candidate['evidence_bundle_sha256']}`",
                f"- Full Stage 3 reconstruction: `{candidate['stage3_reference']}`",
                "",
            ]
        )
        if candidate["interpretation_status"] != "validated":
            lines.append(f"- Detail: {candidate.get('failure_detail', 'No validated interpretation was produced.')}")
            lines.append("")
            continue
        interpretation = candidate["interpretation"]
        note = interpretation["analyst_note"]
        lines.extend(
            [
                "### Analyst note",
                "",
                note["summary"],
                "",
                f"Supporting evidence: {_ids(note['supporting_evidence_ids'])}",
                "",
                "### Interpretive statements",
                "",
            ]
        )
        for statement in interpretation["interpretive_statements"]:
            lines.append(f"- {statement['statement']} Evidence: {_ids(statement['supporting_evidence_ids'])}. Uncertainty: {statement['uncertainty']}")
        evaluation = interpretation["social_process_evaluation"]
        lines.extend(
            [
                "",
                "### Social-process evaluation",
                "",
                f"Result: **`{evaluation['result']}`**",
                "",
                evaluation["rationale"],
                "",
                f"Evaluation evidence: {_ids(evaluation['supporting_evidence_ids'])}",
                "",
            ]
        )
        comparison = evaluation["comparative_rationale"]
        if comparison is not None:
            lines.extend(
                [
                    f"Comparative rationale for `{comparison['primary_hypothesis_id']}`: {comparison['statement']}",
                    "",
                    f"Comparative evidence: {_ids(comparison['evidence_ids'])}",
                    "",
                ]
            )
        for hypothesis in evaluation["hypotheses"]:
            lines.extend(
                [
                    f"#### {hypothesis['hypothesis_id']} — {hypothesis['interpretation_role'].replace('_', ' ')}",
                    "",
                    hypothesis["summary"],
                    "",
                    f"- Proposed confidence: `{hypothesis['proposed_confidence']}`",
                    f"- Deterministic allowed cap: `{hypothesis['allowed_confidence_cap']}`",
                    f"- Displayed confidence: **`{hypothesis['displayed_confidence']}`**",
                    f"- Supported signatures: `{hypothesis['supported_signature_count']}`",
                    f"- Independent evidence groups: `{hypothesis['independent_evidence_group_count']}`",
                    f"- Evidence diversity: **`{hypothesis['evidence_diversity']}`**",
                    f"- Cap reasons: {'; '.join(hypothesis['confidence_cap_reasons']) or 'none'}",
                    f"- Correlated-evidence caveat: {hypothesis['correlated_evidence_caveat'] or 'none'}",
                    "",
                ]
            )
            for signature in hypothesis["supported_signatures"]:
                lines.append(f"- Supported `{signature['signature_id']}`: {signature['rationale']} ({_ids(signature['evidence_ids'])})")
            for counter in hypothesis["contradicted_counter_signatures"]:
                lines.append(f"- Counter-signature `{counter['counter_signature_id']}`: {counter['rationale']} ({_ids(counter['evidence_ids'])})")
            if hypothesis["unknown_signature_ids"]:
                lines.append(f"- Unknown signatures: {_ids(hypothesis['unknown_signature_ids'])}")
            for group in hypothesis["evidence_groups"]:
                lines.append(
                    f"- Evidence group `{group['group_id']}` ({'relational' if group['relational_evidence'] else 'non-relational'}): "
                    f"{group['summary']} Supports {_ids(group['supported_signature_ids'])}; evidence {_ids(group['evidence_ids'])}. "
                    f"Independence basis: {group['independence_rationale']}"
                )
        usage = candidate.get("model_response", {}).get("usage", {})
        lines.extend(
            [
                "",
                "### Model audit",
                "",
                f"- Model returned by API: `{candidate['model_response'].get('model')}`",
                f"- Input tokens: `{usage.get('input_tokens')}`; output tokens: `{usage.get('output_tokens')}`; total tokens: `{usage.get('total_tokens')}`",
                f"- Validation attempt: `{candidate['model_response'].get('validation_attempt')}`; cache reused: `{candidate.get('cache_reused')}`",
                "",
            ]
        )
    return "\n".join(lines)
