"""Versioned Stage 4 configuration loading and validation."""

from __future__ import annotations

import hashlib
import json
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    model: str
    reasoning_effort: str
    store: bool
    max_output_tokens: int
    request_timeout_seconds: int
    max_transport_attempts: int
    max_validation_attempts: int
    transport_backoff_seconds: float


@dataclass(frozen=True)
class InterpretationRules:
    max_hypotheses: int
    minimum_supported_signatures: int
    minimum_substantive_supported_signatures: int
    confidence_levels: tuple[str, ...]
    context_only_confidence_cap: str
    moderate_evidence_diversity_min_groups: int
    high_evidence_diversity_min_groups: int


@dataclass(frozen=True)
class EvidenceConfig:
    max_raw_items: int
    max_text_characters_per_item: int
    max_deterministic_items: int
    max_context_items: int
    max_semantic_examples_per_preceding_event: int
    max_linked_action_examples_per_preceding_event: int
    max_role_agents_per_phase: int


@dataclass(frozen=True)
class CacheConfig:
    reuse_validated_by_default: bool


@dataclass(frozen=True)
class InterpretationConfig:
    schema_version: str
    prompt_version: str
    provider: ProviderConfig
    interpretation: InterpretationRules
    evidence: EvidenceConfig
    cache: CacheConfig

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def fingerprint(self) -> str:
        payload = json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(payload).hexdigest()


def load_config(path: Path) -> InterpretationConfig:
    with Path(path).open("rb") as stream:
        raw = tomllib.load(stream)
    rules = dict(raw["interpretation"])
    rules["confidence_levels"] = tuple(rules["confidence_levels"])
    config = InterpretationConfig(
        schema_version=str(raw["schema_version"]),
        prompt_version=str(raw["prompt_version"]),
        provider=ProviderConfig(**raw["provider"]),
        interpretation=InterpretationRules(**rules),
        evidence=EvidenceConfig(**raw["evidence"]),
        cache=CacheConfig(**raw["cache"]),
    )
    if config.provider.name != "openai":
        raise ValueError(f"unsupported Stage 4 provider: {config.provider.name!r}")
    if not config.provider.model:
        raise ValueError("provider.model must not be empty")
    if config.provider.store:
        raise ValueError("Stage 4 requires provider.store=false")
    if config.provider.max_output_tokens <= 0 or config.provider.request_timeout_seconds <= 0:
        raise ValueError("provider token and timeout limits must be positive")
    if config.provider.max_transport_attempts <= 0 or config.provider.max_validation_attempts <= 0:
        raise ValueError("provider retry limits must be positive")
    if config.provider.transport_backoff_seconds < 0:
        raise ValueError("transport_backoff_seconds must be nonnegative")
    expected = ("low", "moderate", "high")
    if config.interpretation.confidence_levels != expected:
        raise ValueError(f"confidence_levels must be {expected!r} in increasing order")
    if config.interpretation.context_only_confidence_cap not in expected:
        raise ValueError("context_only_confidence_cap is not a configured confidence")
    if config.interpretation.max_hypotheses <= 0:
        raise ValueError("max_hypotheses must be positive")
    if config.interpretation.minimum_supported_signatures < 1:
        raise ValueError("minimum_supported_signatures must be positive")
    if config.interpretation.minimum_substantive_supported_signatures < 1:
        raise ValueError("minimum_substantive_supported_signatures must be positive")
    if config.interpretation.moderate_evidence_diversity_min_groups < 2:
        raise ValueError("moderate evidence diversity must require at least two groups")
    if (
        config.interpretation.high_evidence_diversity_min_groups
        <= config.interpretation.moderate_evidence_diversity_min_groups
    ):
        raise ValueError("high evidence diversity must require more groups than moderate diversity")
    if any(value <= 0 for value in asdict(config.evidence).values()):
        raise ValueError("all evidence limits must be positive")
    return config
