"""Configuration loading and hashing for Stage 3 evidence reconstruction."""

from __future__ import annotations

import hashlib
import json
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class WindowConfig:
    antecedent_minutes: int
    followup_minutes: int
    baseline_minutes: int
    analysis_window_minutes: int


@dataclass(frozen=True)
class SemanticConfig:
    max_features: int
    ngram_min: int
    ngram_max: int
    min_df: int
    background_quantile: float
    threshold_floor: float
    threshold_ceiling: float
    fallback_threshold: float
    min_source_pair_background_pairs: int
    max_matches_per_preceding_event: int
    max_markdown_matches_per_preceding_event: int


@dataclass(frozen=True)
class AntecedentConfig:
    top_n: int
    provisional_score_reference_threshold: float
    minimum_available_components: int
    uptake_agent_cap: int
    novelty_weight: float
    proximity_weight: float
    distinct_agent_uptake_weight: float
    detector_alignment_weight: float
    persistence_weight: float

    @property
    def weights(self) -> dict[str, float]:
        return {
            "novelty": self.novelty_weight,
            "proximity": self.proximity_weight,
            "distinct_agent_uptake": self.distinct_agent_uptake_weight,
            "detector_alignment": self.detector_alignment_weight,
            "persistence": self.persistence_weight,
        }


@dataclass(frozen=True)
class AntecedentSupportConfig:
    moderate_min_fraction: float
    strong_min_fraction: float
    uptake_moderate_other_agents: int
    uptake_strong_other_agents: int
    alignment_moderate: float
    alignment_strong: float
    persistence_moderate: float
    persistence_strong: float
    novelty_moderate: float
    novelty_strong: float


@dataclass(frozen=True)
class StructureConfig:
    minimum_recurring_windows: int
    maximum_recurring_set_size: int
    minimum_specialization_observations: int
    minimum_specialization_windows: int
    maximum_reported_pairs: int
    maximum_reported_sets: int


@dataclass(frozen=True)
class PersistenceConfig:
    minimum_consecutive_windows: int


@dataclass(frozen=True)
class EvidenceReconstructionConfig:
    windows: WindowConfig
    semantics: SemanticConfig
    antecedents: AntecedentConfig
    antecedent_support: AntecedentSupportConfig
    structure: StructureConfig
    persistence: PersistenceConfig

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def fingerprint(self) -> str:
        payload = json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(payload).hexdigest()


def load_config(path: Path) -> EvidenceReconstructionConfig:
    with Path(path).open("rb") as stream:
        raw = tomllib.load(stream)
    config = EvidenceReconstructionConfig(
        windows=WindowConfig(**raw["windows"]),
        semantics=SemanticConfig(**raw["semantics"]),
        antecedents=AntecedentConfig(**raw["antecedents"]),
        antecedent_support=AntecedentSupportConfig(**raw["antecedent_support"]),
        structure=StructureConfig(**raw["structure"]),
        persistence=PersistenceConfig(**raw["persistence"]),
    )
    durations = (
        config.windows.antecedent_minutes,
        config.windows.followup_minutes,
        config.windows.baseline_minutes,
    )
    if any(value <= 0 for value in durations) or config.windows.analysis_window_minutes < 0:
        raise ValueError("Stage 3 window durations must be positive; analysis_window_minutes may be zero to inherit")
    semantic = config.semantics
    if not 0 <= semantic.threshold_floor <= semantic.fallback_threshold <= semantic.threshold_ceiling <= 1:
        raise ValueError("semantic thresholds must satisfy floor <= fallback <= ceiling in [0, 1]")
    if not 0 < semantic.background_quantile < 1:
        raise ValueError("background_quantile must be between zero and one")
    if semantic.max_matches_per_preceding_event <= 0 or semantic.max_markdown_matches_per_preceding_event <= 0:
        raise ValueError("semantic match retention and Markdown display limits must be positive")
    antecedents = config.antecedents
    if antecedents.top_n <= 0 or antecedents.minimum_available_components < 1:
        raise ValueError("antecedent top_n and minimum component count must be positive")
    if not 0 <= antecedents.provisional_score_reference_threshold <= 1:
        raise ValueError("provisional aggregate-score reference threshold must be in [0, 1]")
    if any(weight < 0 for weight in antecedents.weights.values()) or sum(antecedents.weights.values()) <= 0:
        raise ValueError("antecedent weights must be nonnegative with positive total")
    support = config.antecedent_support
    if not 0 <= support.moderate_min_fraction <= support.strong_min_fraction <= 1:
        raise ValueError("antecedent-support fractions must satisfy moderate <= strong in [0, 1]")
    if not 0 <= support.alignment_moderate <= support.alignment_strong <= 1:
        raise ValueError("alignment support thresholds must satisfy moderate <= strong in [0, 1]")
    if not 0 <= support.persistence_moderate <= support.persistence_strong <= 1:
        raise ValueError("persistence support thresholds must satisfy moderate <= strong in [0, 1]")
    if not 0 <= support.novelty_moderate <= support.novelty_strong <= 1:
        raise ValueError("novelty support thresholds must satisfy moderate <= strong in [0, 1]")
    if not 0 <= support.uptake_moderate_other_agents <= support.uptake_strong_other_agents:
        raise ValueError("uptake support thresholds must satisfy moderate <= strong")
    return config
