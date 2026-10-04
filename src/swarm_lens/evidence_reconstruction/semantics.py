"""Deterministic local TF-IDF similarity for process-neutral reconstruction."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import joblib
import numpy as np
from scipy.sparse import csr_matrix
from sklearn.feature_extraction.text import TfidfVectorizer

from .config import SemanticConfig
from .logical_items import source_family


def _actor_key(item: Mapping[str, Any]) -> str | None:
    value = item.get("agent_id") or item.get("agent_name")
    return str(value) if value else None


@dataclass
class SemanticSpace:
    vectorizer: TfidfVectorizer
    item_ids: list[str]
    matrix: csr_matrix
    index_by_id: dict[str, int]
    fit_item_ids: list[str]
    thresholds: dict[str, dict[str, Any]]

    def similarity(self, left_id: str, right_id: str) -> float:
        left = self.matrix[self.index_by_id[left_id]]
        right = self.matrix[self.index_by_id[right_id]]
        return float(left.multiply(right).sum())

    def threshold_for(self, left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, Any]:
        pair = f"{source_family(left)}->{source_family(right)}"
        return self.thresholds.get(pair, self.thresholds["common"])


def _threshold(values: Sequence[float], config: SemanticConfig, *, method: str) -> dict[str, Any]:
    if not values:
        return {
            "value": config.fallback_threshold,
            "pair_count": 0,
            "method": "configured_fallback",
            "quantile": None,
        }
    raw = float(np.quantile(np.asarray(values, dtype=float), config.background_quantile))
    return {
        "value": min(config.threshold_ceiling, max(config.threshold_floor, raw)),
        "pair_count": len(values),
        "method": method,
        "quantile": config.background_quantile,
        "unclamped_quantile_value": raw,
    }


def build_semantic_space(
    items: Sequence[Mapping[str, Any]],
    config: SemanticConfig,
    *,
    model_path: Path | None = None,
) -> SemanticSpace | None:
    text_items = [item for item in items if isinstance(item.get("text"), str) and str(item["text"]).strip()]
    fit_items = [item for item in text_items if item["phase"] in {"baseline", "antecedent"}]
    if not fit_items:
        return None
    vectorizer = TfidfVectorizer(
        lowercase=True,
        strip_accents="unicode",
        stop_words="english",
        ngram_range=(config.ngram_min, config.ngram_max),
        min_df=config.min_df,
        max_features=config.max_features,
        sublinear_tf=True,
        norm="l2",
        token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z0-9_-]{1,}\b",
    )
    try:
        vectorizer.fit([str(item["text"]) for item in fit_items])
    except ValueError:
        return None
    matrix = vectorizer.transform([str(item["text"]) for item in text_items]).tocsr()
    item_ids = [str(item["logical_item_id"]) for item in text_items]
    index_by_id = {item_id: index for index, item_id in enumerate(item_ids)}
    pre_items = [item for item in text_items if item["phase"] in {"baseline", "antecedent"}]
    common_values: list[float] = []
    by_pair: dict[str, list[float]] = {}
    for left_index, left in enumerate(pre_items):
        for right in pre_items[left_index + 1 :]:
            left_actor = _actor_key(left)
            right_actor = _actor_key(right)
            if left_actor is not None and left_actor == right_actor:
                continue
            similarity = float(matrix[index_by_id[left["logical_item_id"]]].multiply(matrix[index_by_id[right["logical_item_id"]]]).sum())
            common_values.append(similarity)
            pair = f"{source_family(left)}->{source_family(right)}"
            by_pair.setdefault(pair, []).append(similarity)
    thresholds = {"common": _threshold(common_values, config, method="pre_boundary_common_quantile")}
    for pair in ("chat->chat", "chat->session_goal", "session_goal->chat", "session_goal->session_goal"):
        values = by_pair.get(pair, [])
        if len(values) >= config.min_source_pair_background_pairs:
            thresholds[pair] = _threshold(values, config, method="pre_boundary_source_pair_quantile")
        else:
            thresholds[pair] = {
                **thresholds["common"],
                "method": "common_threshold_fallback",
                "source_pair_background_pair_count": len(values),
                "minimum_source_pair_background_pairs": config.min_source_pair_background_pairs,
            }
    if model_path is not None:
        model_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(vectorizer, model_path)
    return SemanticSpace(
        vectorizer=vectorizer,
        item_ids=item_ids,
        matrix=matrix,
        index_by_id=index_by_id,
        fit_item_ids=[str(item["logical_item_id"]) for item in fit_items],
        thresholds=thresholds,
    )


def novelty_score(
    item: Mapping[str, Any],
    baseline_items: Sequence[Mapping[str, Any]],
    semantic_space: SemanticSpace | None,
) -> tuple[float | None, dict[str, Any] | None]:
    if semantic_space is None or item["logical_item_id"] not in semantic_space.index_by_id:
        return None, None
    eligible = [row for row in baseline_items if row["logical_item_id"] in semantic_space.index_by_id]
    if not eligible:
        return None, None
    scored = [(semantic_space.similarity(item["logical_item_id"], row["logical_item_id"]), row) for row in eligible]
    similarity, match = max(scored, key=lambda value: (value[0], value[1]["logical_item_id"]))
    return max(0.0, 1.0 - similarity), {
        "logical_item_id": match["logical_item_id"],
        "similarity": similarity,
        "source_type_pair": f"{source_family(item)}->{source_family(match)}",
        "provenance": match["provenance"],
    }


def later_semantic_matches(
    item: Mapping[str, Any],
    later_items: Sequence[Mapping[str, Any]],
    semantic_space: SemanticSpace | None,
    *,
    maximum_matches: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if semantic_space is None or item["logical_item_id"] not in semantic_space.index_by_id:
        return [], {"eligible_later_text_items": 0, "matched_items": 0, "thresholds_available": False}
    matches: list[dict[str, Any]] = []
    eligible_count = 0
    for later in later_items:
        if later["timestamp"] <= item["timestamp"] or later["logical_item_id"] not in semantic_space.index_by_id:
            continue
        eligible_count += 1
        similarity = semantic_space.similarity(item["logical_item_id"], later["logical_item_id"])
        threshold = semantic_space.threshold_for(item, later)
        if similarity + 1e-12 < float(threshold["value"]):
            continue
        matches.append(
            {
                "logical_item_id": later["logical_item_id"],
                "timestamp": later["timestamp"],
                "minutes_after_preceding_event": (later["timestamp"] - item["timestamp"]).total_seconds() / 60,
                "phase": later["phase"],
                "agent_id": later.get("agent_id"),
                "agent_name": later.get("agent_name"),
                "source_type": later["source_type"],
                "source_type_pair": f"{source_family(item)}->{source_family(later)}",
                "similarity": similarity,
                "threshold": threshold["value"],
                "threshold_method": threshold["method"],
                "text": later.get("text"),
                "computer_use_session_id": later.get("computer_use_session_id"),
                "provenance": later["provenance"],
            }
        )
    matches.sort(key=lambda row: (-row["similarity"], row["timestamp"], row["logical_item_id"]))
    total_matches = len(matches)
    return matches[:maximum_matches], {
        "eligible_later_text_items": eligible_count,
        "matched_items": total_matches,
        "retained_highest_scoring_matches": min(total_matches, maximum_matches),
        "thresholds_available": True,
    }


def finite_or_none(value: float | None) -> float | None:
    return value if value is not None and math.isfinite(value) else None
