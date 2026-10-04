from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from swarm_lens.research_fingerprint import (
    _canonical_hash,
    research_content_fingerprint,
)


ROOT = Path(__file__).resolve().parents[1]
EPISODES = (
    "perform-novel-research",
    "connect-your-worlds-into-a-3d-universe",
)


@pytest.mark.parametrize("episode_slug", EPISODES)
def test_fingerprint_is_deterministic_and_research_order_is_contiguous(
    episode_slug: str,
) -> None:
    first, payload = research_content_fingerprint(ROOT, episode_slug)
    second, repeated = research_content_fingerprint(ROOT, episode_slug)
    assert first == second
    assert payload == repeated
    assert [
        row["rank"]
        for row in payload["behavioral_change_detection"]["candidates"]
    ] == [1, 2, 3, 4, 5]
    assert [
        row["rank"] for row in payload["analyst_interpretation"]["candidates"]
    ] == [1, 2, 3, 4, 5]


@pytest.mark.parametrize("episode_slug", EPISODES)
def test_analytical_change_changes_fingerprint(episode_slug: str) -> None:
    fingerprint, payload = research_content_fingerprint(ROOT, episode_slug)
    changed = deepcopy(payload)
    changed["behavioral_change_detection"]["candidates"][0]["aggregate_score"] += 1
    assert _canonical_hash(changed) != fingerprint


def test_fingerprint_module_does_not_read_frontend_view_models() -> None:
    source = (ROOT / "src" / "swarm_lens" / "research_fingerprint.py").read_text(
        encoding="utf-8"
    )
    assert "frontend/public/data" not in source
