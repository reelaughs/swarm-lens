"""Configuration loading and hashing for the turning-point detector."""

from __future__ import annotations

import hashlib
import json
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TopicModelConfig:
    n_components: int
    min_df: int
    max_df: float
    max_features: int
    ngram_min: int
    ngram_max: int
    top_terms: int
    max_iter: int


@dataclass(frozen=True)
class DetectorConfig:
    window_sizes_minutes: tuple[int, ...]
    overall_min_high_level_events: int
    overall_min_distinct_agents: int
    communication_min_documents_per_window: int
    intention_min_documents_per_window: int
    participation_min_agent_events_per_window: int
    participation_min_distinct_agents: int
    action_type_min_events_per_window: int
    min_components_for_aggregate: int
    min_valid_comparisons: int
    min_peak_separation_minutes: int
    top_k: int
    top_changes: int
    random_seed: int


@dataclass(frozen=True)
class TurningPointConfig:
    detector: DetectorConfig
    communication_model: TopicModelConfig
    intention_model: TopicModelConfig

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def fingerprint(self) -> str:
        payload = json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(payload).hexdigest()


def _topic(section: dict[str, Any]) -> TopicModelConfig:
    return TopicModelConfig(**section)


def load_config(path: Path) -> TurningPointConfig:
    with Path(path).open("rb") as stream:
        raw = tomllib.load(stream)
    detector_raw = dict(raw["detector"])
    detector_raw["window_sizes_minutes"] = tuple(detector_raw["window_sizes_minutes"])
    config = TurningPointConfig(
        detector=DetectorConfig(**detector_raw),
        communication_model=_topic(raw["communication_model"]),
        intention_model=_topic(raw["intention_model"]),
    )
    if not config.detector.window_sizes_minutes or any(size <= 0 for size in config.detector.window_sizes_minutes):
        raise ValueError("window sizes must be positive")
    if not 1 <= config.detector.min_components_for_aggregate <= 4:
        raise ValueError("min_components_for_aggregate must be between 1 and 4")
    if config.detector.min_valid_comparisons < 2:
        raise ValueError("min_valid_comparisons must be at least 2")
    return config
