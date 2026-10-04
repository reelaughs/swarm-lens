from __future__ import annotations

from pathlib import Path

from swarm_lens.execution.jobs import JobRegistry


def scope() -> dict:
    return {
        "scope_id": "goal-1",
        "slug": "example",
        "title": "Example",
        "start": "2026-01-01T00:00:00+00:00",
        "end": "2026-01-02T00:00:00+00:00",
        "runnable": True,
        "warnings": [],
        "blocking_reason": None,
    }


def test_registry_persists_isolated_dataset_and_run_paths(tmp_path: Path) -> None:
    registry = JobRegistry(tmp_path / "registry.sqlite3")
    dataset = registry.create_dataset("ai_village")
    registry.replace_scopes(dataset["id"], [scope()])
    registry.update_dataset(dataset["id"], status="ready_for_episode_selection")
    first = registry.create_run(dataset["id"], scope(), run_root=tmp_path / "runs")
    second = registry.create_run(dataset["id"], scope(), run_root=tmp_path / "runs")
    assert first["id"] != second["id"]
    assert first["log_path"] != second["log_path"]
    assert Path(first["log_path"]).is_relative_to(tmp_path / "runs")


def test_running_work_is_recovered_as_interrupted_and_retryable(tmp_path: Path) -> None:
    registry = JobRegistry(tmp_path / "registry.sqlite3")
    dataset = registry.create_dataset("ai_village")
    registry.replace_scopes(dataset["id"], [scope()])
    registry.update_dataset(dataset["id"], status="ready_for_episode_selection")
    run = registry.create_run(dataset["id"], scope(), run_root=tmp_path / "runs")
    registry.update_run(run["id"], status="running", phase="reconstructing_evidence")
    assert registry.recover_interrupted_runs() == 1
    recovered = registry.get_run(run["id"])
    assert recovered["status"] == "failed"
    assert recovered["failure_kind"] == "interrupted_worker"
    assert recovered["retryable"] is True
