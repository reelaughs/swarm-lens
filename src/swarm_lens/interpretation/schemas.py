"""Strict model-output structures for Stage 4."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AnalystNote(StrictModel):
    summary: str = Field(min_length=1)
    supporting_evidence_ids: list[str] = Field(min_length=1)


class InterpretiveStatement(StrictModel):
    statement: str = Field(min_length=1)
    supporting_evidence_ids: list[str] = Field(min_length=1)
    uncertainty: str = Field(min_length=1)


class SupportedSignature(StrictModel):
    signature_id: str
    rationale: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)


class ContradictedCounterSignature(StrictModel):
    counter_signature_id: str
    rationale: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)


class AlternativeExplanation(StrictModel):
    summary: str = Field(min_length=1)
    evidence_ids: list[str]


class EvidenceGroup(StrictModel):
    group_id: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    supported_signature_ids: list[str] = Field(min_length=1)
    independence_rationale: str = Field(min_length=1)
    relational_evidence: bool


class ProposedHypothesis(StrictModel):
    hypothesis_id: str
    interpretation_role: Literal["best_supported_candidate", "plausible_alternative"]
    proposed_confidence: Literal["low", "moderate", "high"]
    summary: str = Field(min_length=1)
    supported_signatures: list[SupportedSignature]
    contradicted_counter_signatures: list[ContradictedCounterSignature]
    unknown_signature_ids: list[str]
    alternative_explanations: list[AlternativeExplanation]
    caveats: list[str]
    evidence_groups: list[EvidenceGroup] = Field(min_length=1)


class SocialProcessEvaluation(StrictModel):
    result: Literal["candidate_hypotheses", "no_clear_social_process_match"]
    rationale: str = Field(min_length=1)
    supporting_evidence_ids: list[str]
    hypotheses: list[ProposedHypothesis]


class ModelInterpretation(StrictModel):
    schema_version: Literal["1.1"]
    analyst_note: AnalystNote
    interpretive_statements: list[InterpretiveStatement]
    social_process_evaluation: SocialProcessEvaluation


def response_json_schema() -> dict:
    """Return the Pydantic-derived schema accepted by Responses Structured Outputs."""

    return ModelInterpretation.model_json_schema()
