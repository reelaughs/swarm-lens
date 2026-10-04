from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "build_frontend_view_model.py"
SPEC = importlib.util.spec_from_file_location("build_frontend_view_model", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


MANIFEST_PATH = ROOT / "configs" / "frontend_episode_artifacts.toml"
EPISODES = {
    "perform-novel-research": {
        1: "6d50d54e63018955ebd93fc1",
        2: "625641230f110578e7d1314b",
        3: "3ebf55addfb880066a3e19c9",
        4: "679a792ad7284b2278aae8a5",
        5: "02e3cf794218704efcfc478c",
    },
    "connect-your-worlds-into-a-3d-universe": {
        1: "a7440bb26755c833f9e8ae9c",
        2: "c510c0e37c61f4bd192ab183",
        3: "3b024d33b29fb19e6e6726f6",
        4: "20047a5fe0c26ba78a1217e4",
        5: "1ba38242ae6ccb287056e6ce",
    },
}


def test_frozen_cache_manifest_is_explicit_for_both_episodes() -> None:
    for slug, expected in EPISODES.items():
        episode = MODULE._load_episode_artifacts(MANIFEST_PATH, slug)
        assert episode["candidate_ranks"] == [1, 2, 3, 4, 5]
        assert episode["stage4_cache_keys"] == expected


def test_adapter_does_not_reference_evaluation_packet() -> None:
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    assert "evaluation_packet" not in source


@pytest.mark.parametrize("episode_slug", EPISODES)
def test_view_model_preserves_rank_and_stage25_descriptions(episode_slug: str) -> None:
    view_model = MODULE.build_view_model(ROOT, episode_slug, MANIFEST_PATH)
    brief = json.loads(
        (
            ROOT
            / "outputs"
            / "episodes"
            / episode_slug
            / "turning_points"
            / "candidate_brief.json"
        ).read_text(encoding="utf-8")
    )
    brief_by_rank = {item["rank"]: item for item in brief["candidates"]}

    assert [item["rank"] for item in view_model["turningPoints"]] == [1, 2, 3, 4, 5]
    for item in view_model["turningPoints"]:
        assert item["deterministicDescriptions"] == brief_by_rank[item["rank"]][
            "deterministic_change_description"
        ]
        assert "strongestDeterministicDescription" not in item


@pytest.mark.parametrize("episode_slug", EPISODES)
def test_stage4_references_have_provenance_and_roles_are_preserved(episode_slug: str) -> None:
    view_model = MODULE.build_view_model(ROOT, episode_slug, MANIFEST_PATH)
    for item in view_model["turningPoints"]:
        references = item["referencedEvidence"]
        assert references
        assert all(value["evidenceId"] for value in references)
        assert all(value["provenance"] is not None for value in references)
        hypotheses = item["interpretation"]["socialProcessEvaluation"]["hypotheses"]
        if hypotheses:
            assert sum(
                value["interpretation_role"] == "best_supported_candidate"
                for value in hypotheses
            ) == 1
            assert all(value["display_name"] for value in hypotheses)
            assert all("displayed_confidence" in value for value in hypotheses)
            assert all("evidence_diversity" in value for value in hypotheses)


@pytest.mark.parametrize("episode_slug", EPISODES)
def test_unknown_and_contradicted_signatures_remain_separate(episode_slug: str) -> None:
    view_model = MODULE.build_view_model(ROOT, episode_slug, MANIFEST_PATH)
    for item in view_model["turningPoints"]:
        for hypothesis in item["interpretation"]["socialProcessEvaluation"]["hypotheses"]:
            assert "unknown_signature_ids" in hypothesis
            assert "contradicted_counter_signatures" in hypothesis
            assert isinstance(hypothesis["unknown_signature_ids"], list)
            assert isinstance(hypothesis["contradicted_counter_signatures"], list)


@pytest.mark.parametrize("episode_slug", EPISODES)
def test_output_is_deterministic(tmp_path: Path, episode_slug: str) -> None:
    first = tmp_path / f"{episode_slug}-first.json"
    second = tmp_path / f"{episode_slug}-second.json"
    MODULE.write_view_model(ROOT, first, episode_slug, MANIFEST_PATH)
    MODULE.write_view_model(ROOT, second, episode_slug, MANIFEST_PATH)
    assert first.read_bytes() == second.read_bytes()


def test_schema_describes_the_reusable_frozen_episode_contract() -> None:
    schema = json.loads(
        (ROOT / "schemas" / "frontend_episode_view_model.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert schema["properties"]["viewModelVersion"]["const"] == "1.0"
    assert schema["properties"]["turningPoints"]["minItems"] == 1
    assert "maxItems" not in schema["properties"]["turningPoints"]
    assert schema["$defs"]["episode"]["properties"]["slug"]["pattern"]
    assert schema["$defs"]["episode"]["properties"]["turningPointCount"]["minimum"] == 1
    required = set(schema["$defs"]["turningPoint"]["required"])
    assert {"rank", "signals", "deterministicDescriptions", "interpretation"} <= required
