"""Candidate reconstruction windows and inactive-gap clipping."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Mapping, Sequence


def active_segment(
    boundary: datetime,
    *,
    episode_start: datetime,
    episode_end: datetime,
    inactive_gaps: Sequence[Mapping[str, Any]],
) -> tuple[datetime, datetime]:
    """Return the gap-free episode segment containing the boundary."""
    start = episode_start
    end = episode_end
    for gap in sorted(inactive_gaps, key=lambda row: row["start"]):
        if gap["end"] <= boundary:
            start = max(start, gap["end"])
        elif gap["start"] >= boundary:
            end = min(end, gap["start"])
            break
        elif gap["start"] < boundary < gap["end"]:
            raise ValueError("turning-point boundary lies inside an inactive gap")
    return start, end


def reconstruction_intervals(
    boundary: datetime,
    *,
    episode_start: datetime,
    episode_end: datetime,
    inactive_gaps: Sequence[Mapping[str, Any]],
    antecedent_minutes: int,
    followup_minutes: int,
    baseline_minutes: int,
) -> dict[str, Any]:
    segment_start, segment_end = active_segment(
        boundary,
        episode_start=episode_start,
        episode_end=episode_end,
        inactive_gaps=inactive_gaps,
    )
    requested_antecedent_start = boundary - timedelta(minutes=antecedent_minutes)
    requested_baseline_start = requested_antecedent_start - timedelta(minutes=baseline_minutes)
    requested_followup_end = boundary + timedelta(minutes=followup_minutes)
    antecedent_start = max(requested_antecedent_start, segment_start)
    baseline_start = max(requested_baseline_start, segment_start)
    baseline_end = min(requested_antecedent_start, antecedent_start)
    followup_end = min(requested_followup_end, segment_end)
    return {
        "active_segment_start": segment_start,
        "active_segment_end": segment_end,
        "baseline_start": baseline_start,
        "baseline_end": baseline_end,
        "antecedent_start": antecedent_start,
        "antecedent_end": boundary,
        "followup_start": boundary,
        "followup_end": followup_end,
        "requested": {
            "baseline_start": requested_baseline_start,
            "antecedent_start": requested_antecedent_start,
            "followup_end": requested_followup_end,
        },
        "coverage_minutes": {
            "baseline": max(0.0, (baseline_end - baseline_start).total_seconds() / 60),
            "antecedent": max(0.0, (boundary - antecedent_start).total_seconds() / 60),
            "followup": max(0.0, (followup_end - boundary).total_seconds() / 60),
        },
        "truncated_by_inactive_gap": {
            "baseline": baseline_start > requested_baseline_start or baseline_end < requested_antecedent_start,
            "antecedent": antecedent_start > requested_antecedent_start,
            "followup": followup_end < requested_followup_end,
        },
    }


def make_subwindows(start: datetime, end: datetime, minutes: int) -> list[dict[str, Any]]:
    windows = []
    index = 0
    cursor = start
    while cursor < end:
        window_end = min(cursor + timedelta(minutes=minutes), end)
        windows.append({"index": index, "start": cursor, "end": window_end})
        cursor = window_end
        index += 1
    return windows
