from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from swarm_lens.execution.jobs import JobRegistry
from swarm_lens.execution.runner import PipelineRunner, WorkspaceLayout
from swarm_lens.ingestion import BuildResult, Episode, parse_timestamp
from swarm_lens.interpretation.provider import ProviderResponse


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def short_workspace():
    path = Path(tempfile.mkdtemp(prefix="sl-"))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def test_deterministic_runner_calls_existing_pipeline_functions_and_pauses(
    tmp_path: Path, monkeypatch
) -> None:
    registry = JobRegistry(tmp_path / "registry.sqlite3")
    dataset = registry.create_dataset("ai_village")
    scope = {
        "scope_id": "goal-1",
        "title": "Example",
        "start": "2026-01-01T00:00:00+00:00",
        "end": "2026-01-02T00:00:00+00:00",
        "slug": "example",
        "runnable": True,
        "warnings": [],
        "blocking_reason": None,
    }
    registry.replace_scopes(dataset["id"], [scope])
    registry.update_dataset(dataset["id"], status="ready_for_episode_selection")
    layout = WorkspaceLayout.under(ROOT, tmp_path / "workspace")
    run = registry.create_run(dataset["id"], scope, run_root=layout.output_root)
    calls: list[str] = []

    class Adapter:
        def materialize_scope(self, **kwargs):
            calls.append("materialize")
            path = kwargs["processed_root"] / "example" / "events.parquet"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
            episode = Episode(
                "goal-1",
                "village-1",
                "Example",
                parse_timestamp("2026-01-01 00:00:00", field="start"),
                parse_timestamp("2026-01-02 00:00:00", field="end"),
                "example",
            )
            return BuildResult(episode, path, kwargs["output_root"] / "example" / "ingestion_validation.md", 1)

        def contextual_inputs(self, raw_dir):
            return {"raw_dir": raw_dir, "changelog_path": raw_dir / "CHANGELOG.md"}

    monkeypatch.setattr("swarm_lens.execution.runner.adapter_for", lambda *args, **kwargs: Adapter())

    def fake_detection(**kwargs):
        calls.append("detect")
        turning = kwargs["output_root"] / "example" / "turning_points"
        turning.mkdir(parents=True, exist_ok=True)
        pq.write_table(pa.Table.from_pylist([{"rank": 1}]), turning / "top_candidates.parquet")
        (turning / "resolved_configuration.json").write_text(
            json.dumps({"configuration_sha256": "a" * 64, "canonical_input_sha256": "b" * 64}),
            encoding="utf-8",
        )
        (turning / "inactive_gaps.csv").write_text("window_size_minutes,start,end,duration_minutes\n", encoding="utf-8")
        return SimpleNamespace(recommended_window_minutes=30, candidate_count=1)

    monkeypatch.setattr("swarm_lens.execution.runner.run_detection", fake_detection)
    monkeypatch.setattr("swarm_lens.execution.runner.export_candidate_context", lambda **kwargs: calls.append("context"))
    monkeypatch.setattr("swarm_lens.execution.runner.export_candidate_brief", lambda **kwargs: calls.append("brief"))
    monkeypatch.setattr("swarm_lens.execution.runner.run_reconstruction", lambda **kwargs: calls.append("reconstruct"))

    PipelineRunner(registry=registry, layout=layout).run_deterministic(run["id"])
    assert calls == ["materialize", "detect", "context", "brief", "reconstruct"]
    finished = registry.get_run(run["id"])
    assert finished["status"] == "awaiting_interpretation_approval"
    assert finished["phase"] == "deterministic_analysis_complete"


def test_interpretation_resume_uses_injected_provider_and_packages_runtime_manifest(
    tmp_path: Path, short_workspace: Path, monkeypatch
) -> None:
    registry = JobRegistry(tmp_path / "registry.sqlite3")
    dataset = registry.create_dataset("ai_village")
    scope = {
        "scope_id": "goal-1",
        "title": "Example",
        "start": "2026-01-01T00:00:00+00:00",
        "end": "2026-01-02T00:00:00+00:00",
        "slug": "example",
        "runnable": True,
        "warnings": [],
        "blocking_reason": None,
    }
    registry.replace_scopes(dataset["id"], [scope])
    registry.update_dataset(dataset["id"], status="ready_for_episode_selection")
    layout = WorkspaceLayout.under(ROOT, short_workspace)
    run = registry.create_run(dataset["id"], scope, run_root=layout.output_root)
    registry.update_run(
        run["id"],
        status="awaiting_interpretation_approval",
        phase="deterministic_analysis_complete",
    )
    stage3_path = (
        layout.run_episodes(run["id"])
        / "example"
        / "turning_points"
        / "evidence_reconstruction"
        / "evidence_reconstruction.json"
    )
    stage3_path.parent.mkdir(parents=True)
    stage3_path.write_text(
        json.dumps(
            {
                "metadata": {
                    "episode_slug": "example",
                    "episode_goal": "Example",
                    "episode_goal_id": "goal-1",
                },
                "candidates": [
                    {
                        "rank": 1,
                        "comparison_id": "30m:test",
                        "turning_point_timestamp": "2026-01-01T01:00:00+00:00",
                        "aggregate_score": 1.0,
                        "detector_component_scores": {},
                        "windows": {},
                        "ranked_preceding_events": [],
                        "chronological_evidence_sequence": [],
                        "actor_and_structure": {},
                        "explicit_address_relationships": {},
                        "role_task_asymmetry": {},
                        "external_context": {"events": []},
                        "null_findings": [],
                        "caveats": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    calls = []

    class FakeProvider:
        def generate(self, *, instructions, user_input, schema):
            calls.append(user_input)
            payload = {
                "schema_version": "1.2",
                "analyst_note": {
                    "summary": "The evidence shows a change without a clear social-process match.",
                    "supporting_evidence_ids": ["swl-d-0001"],
                },
                "interpretive_statements": [
                    {
                        "statement": "The bounded record supports more than one interpretation.",
                        "supporting_evidence_ids": ["swl-d-0001"],
                        "uncertainty": "The evidence window is limited.",
                    }
                ],
                "social_process_evaluation": {
                    "result": "no_clear_social_process_match",
                    "rationale": "No library hypothesis clears the evidence floor.",
                    "supporting_evidence_ids": ["swl-d-0001"],
                    "hypotheses": [],
                    "comparative_rationale": None,
                },
            }
            text = json.dumps(payload)
            return ProviderResponse(
                "resp-fake",
                "fake-model",
                "completed",
                text,
                None,
                {"input_tokens": 10, "output_tokens": 10, "total_tokens": 20},
                {"id": "resp-fake", "model": "fake-model", "status": "completed", "usage": {}},
            )

    class FakePresentation:
        @staticmethod
        def write_view_model(root, output_path, episode_slug, manifest_path, **kwargs):
            assert manifest_path.is_file()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps({"viewModelVersion": "1.0", "episode": {"slug": episode_slug}}),
                encoding="utf-8",
            )

    monkeypatch.setattr(
        "swarm_lens.execution.runner._load_presentation_module",
        lambda repository_root: FakePresentation(),
    )
    PipelineRunner(registry=registry, layout=layout).run_interpretation_and_package(
        run["id"], provider_factory=lambda _: FakeProvider()
    )
    completed = registry.get_run(run["id"])
    assert completed["status"] == "completed"
    assert calls and "BEGIN_UNTRUSTED_EVIDENCE_DATA" in calls[0]
    assert (layout.run_dir(run["id"]) / "runtime_artifacts.toml").is_file()
    assert Path(completed["view_model_path"]).is_file()
