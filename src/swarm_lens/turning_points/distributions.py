"""Distribution construction, divergence, and robust standardization."""

from __future__ import annotations

import math
import statistics
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import numpy as np
from scipy.spatial.distance import jensenshannon


def normalize_distribution(values: Iterable[float]) -> np.ndarray | None:
    array = np.asarray(list(values), dtype=float)
    if array.ndim != 1 or np.any(~np.isfinite(array)) or np.any(array < 0):
        raise ValueError("distribution values must be a finite, nonnegative vector")
    total = float(array.sum())
    return None if total <= 0 else array / total


def count_distribution(counts: Mapping[str, int], vocabulary: Sequence[str]) -> np.ndarray | None:
    return normalize_distribution(counts.get(item, 0) for item in vocabulary)


def js_divergence(before: Sequence[float] | np.ndarray, after: Sequence[float] | np.ndarray) -> float:
    p = normalize_distribution(before)
    q = normalize_distribution(after)
    if p is None or q is None or p.shape != q.shape:
        raise ValueError("Jensen-Shannon inputs must be nonempty vectors of equal length")
    return float(jensenshannon(p, q, base=2.0) ** 2)


def robust_standardize(
    values: Sequence[float | None],
    *,
    min_valid: int,
) -> tuple[list[float | None], dict[str, Any]]:
    valid = [float(value) for value in values if value is not None]
    metadata: dict[str, Any] = {
        "valid_count": len(valid),
        "min_required": min_valid,
        "reliable": len(valid) >= min_valid,
        "center": None,
        "scale": None,
        "scale_method": None,
    }
    if len(valid) < min_valid:
        return [None] * len(values), metadata
    center = statistics.median(valid)
    mad = statistics.median(abs(value - center) for value in valid)
    scale = 1.4826 * mad
    method = "mad"
    if scale == 0:
        scale = statistics.stdev(valid) if len(valid) > 1 else 0.0
        method = "sample_std_fallback"
    metadata.update(center=center, scale=scale, scale_method=method)
    if scale == 0:
        metadata["scale_method"] = "constant_zero"
        return [0.0 if value is not None else None for value in values], metadata
    return [None if value is None else (float(value) - center) / scale for value in values], metadata


def aggregate_available(
    component_scores: Mapping[str, float | None],
    *,
    minimum_components: int,
) -> tuple[float | None, tuple[str, ...]]:
    available = tuple(name for name, value in component_scores.items() if value is not None)
    if len(available) < minimum_components:
        return None, available
    return statistics.fmean(float(component_scores[name]) for name in available), available
