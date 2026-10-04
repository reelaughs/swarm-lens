from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from swarm_lens.api import APISettings, create_app
from swarm_lens.datasets.secure_upload import UploadLimits
from swarm_lens.execution.jobs import JobRegistry

from upload_fixtures import make_ai_village_raw, zip_raw


ROOT = Path(__file__).resolve().parents[1]


class FakeWorkerManager:
    def __init__(self) -> None:
        self.busy = False
        self.started = False
        self.deterministic: list[str] = []
        self.interpretations: list[str] = []

    def start(self) -> None:
        self.started = True

    def submit_deterministic(self, run_id: str) -> None:
        self.deterministic.append(run_id)

    def submit_interpretation(self, run_id: str) -> None:
        self.interpretations.append(run_id)


def setup(tmp_path: Path):
    registry = JobRegistry(tmp_path / "registry.sqlite3")
    manager = FakeWorkerManager()
    settings = APISettings(
        repository_root=ROOT,
        workspace_root=tmp_path / "workspace",
        registry_path=registry.path,
        upload_limits=UploadLimits(),
    )
    return registry, manager, TestClient(
        create_app(settings, registry=registry, worker_manager=manager)
    )


def test_upload_validate_choose_run_and_pause_before_interpretation(tmp_path: Path) -> None:
    raw = make_ai_village_raw(tmp_path / "fixture")
    archive = zip_raw(raw, tmp_path / "bundle.zip")
    registry, manager, client_context = setup(tmp_path)
    with client_context as client, archive.open("rb") as stream:
        response = client.post(
            "/api/datasets",
            data={"adapter_id": "ai_village"},
            files={"bundle": ("bundle.zip", stream, "application/zip")},
        )
        assert response.status_code == 202
        dataset_id = response.json()["id"]
        dataset = client.get(f"/api/datasets/{dataset_id}").json()
        assert dataset["status"] == "ready_for_episode_selection"
        scopes = client.get(f"/api/datasets/{dataset_id}/scopes").json()["scopes"]
        runnable = next(scope for scope in scopes if scope["scope_id"] == "goal-runnable")
        run_response = client.post(
            "/api/runs", json={"dataset_id": dataset_id, "scope_id": runnable["scope_id"]}
        )
        assert run_response.status_code == 202
        run_id = run_response.json()["id"]
        assert manager.deterministic == [run_id]

        registry.update_run(
            run_id,
            status="awaiting_interpretation_approval",
            phase="deterministic_analysis_complete",
        )
        paused = client.get(f"/api/runs/{run_id}").json()
        assert paused["interpretation_requires_approval"] is True
        assert manager.interpretations == []

        approved = client.post(f"/api/runs/{run_id}/interpret")
        assert approved.status_code == 202
        assert approved.json()["status"] == "interpreting"
        assert manager.interpretations == [run_id]


def test_completed_runtime_view_model_is_served_only_after_completion(tmp_path: Path) -> None:
    registry, manager, client_context = setup(tmp_path)
    dataset = registry.create_dataset("ai_village")
    scope = {
        "scope_id": "goal-1",
        "title": "Runtime episode",
        "start": "2026-01-01T00:00:00+00:00",
        "end": "2026-01-02T00:00:00+00:00",
        "slug": "runtime-episode",
        "runnable": True,
        "warnings": [],
        "blocking_reason": None,
    }
    registry.replace_scopes(dataset["id"], [scope])
    registry.update_dataset(dataset["id"], status="ready_for_episode_selection")
    run = registry.create_run(dataset["id"], scope, run_root=tmp_path / "workspace" / "outputs" / "runs")
    view = tmp_path / "workspace" / "outputs" / "runs" / run["id"] / "presentation" / "runtime-episode.json"
    view.parent.mkdir(parents=True)
    view.write_text(json.dumps({"viewModelVersion": "1.0"}), encoding="utf-8")
    with client_context as client:
        assert client.get(f"/api/runs/{run['id']}/view-model").status_code == 409
        registry.update_run(
            run["id"],
            status="completed",
            phase="completed",
            view_model_path=str(view),
        )
        response = client.get(f"/api/runs/{run['id']}/view-model")
        assert response.status_code == 200
        assert response.json()["viewModelVersion"] == "1.0"
