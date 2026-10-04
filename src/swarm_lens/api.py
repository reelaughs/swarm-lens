"""Thin local HTTP API around the existing SwarmLens Python pipeline."""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel

from swarm_lens.datasets import UploadLimits, install_zip_bundle, stage_upload
from swarm_lens.datasets.ai_village import adapter_for
from swarm_lens.datasets.secure_upload import BundleValidationError, StagedUpload
from swarm_lens.execution import JobRegistry, WorkerBusyError, WorkerManager, WorkspaceLayout


@dataclass(frozen=True)
class APISettings:
    repository_root: Path
    workspace_root: Path
    registry_path: Path
    upload_limits: UploadLimits = field(default_factory=UploadLimits)
    max_log_response_bytes: int = 64 * 1024

    @classmethod
    def local(cls, repository_root: Path) -> "APISettings":
        root = Path(repository_root).resolve()
        return cls(
            repository_root=root,
            workspace_root=root,
            registry_path=root / "var" / "swarmlens.sqlite3",
        )


class RunRequest(BaseModel):
    dataset_id: str
    scope_id: str


def _public_dataset(value: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value.get(key)
        for key in (
            "id",
            "adapter_id",
            "status",
            "created_at",
            "updated_at",
            "validation",
            "error",
        )
    }


def _public_run(value: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value.get(key)
        for key in (
            "id",
            "dataset_id",
            "scope_id",
            "episode_slug",
            "status",
            "phase",
            "created_at",
            "updated_at",
            "retryable",
            "failure_kind",
            "error",
        )
    } | {
        "interpretation_requires_approval": value.get("status")
        == "awaiting_interpretation_approval",
        "view_model_available": value.get("status") == "completed"
        and bool(value.get("view_model_path")),
    }


def create_app(
    settings: APISettings | None = None,
    *,
    registry: JobRegistry | None = None,
    worker_manager: WorkerManager | None = None,
) -> FastAPI:
    root = Path(__file__).resolve().parents[2]
    settings = settings or APISettings.local(root)
    layout = WorkspaceLayout.under(settings.repository_root, settings.workspace_root)
    registry = registry or JobRegistry(settings.registry_path)
    worker_manager = worker_manager or WorkerManager(
        repository_root=settings.repository_root,
        registry=registry,
        workspace_root=settings.workspace_root,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        worker_manager.start()
        yield

    app = FastAPI(title="SwarmLens local analysis API", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.registry = registry
    app.state.worker_manager = worker_manager

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/capabilities")
    def capabilities() -> dict[str, Any]:
        return {
            "adapters": [
                {
                    "id": "ai_village",
                    "label": "AI Village ZIP",
                    "scope_types": ["episode"],
                    "custom_windows_supported": False,
                }
            ],
            "upload_limits": asdict(settings.upload_limits),
            "interpretation_requires_explicit_approval": True,
        }

    def validate_staged(dataset_id: str, adapter_id: str, staged: StagedUpload) -> None:
        registry.update_dataset(dataset_id, status="validating")
        try:
            adapter = adapter_for(adapter_id, repository_root=settings.repository_root)
            permanent, inspection = install_zip_bundle(
                staged,
                uploads_root=layout.uploads_root,
                limits=settings.upload_limits,
                validate_extracted=adapter.inspect,
            )
            value = inspection.as_dict()
            value["upload"] = {
                "compressed_bytes": staged.compressed_bytes,
                "archive_sha256": staged.archive_sha256,
            }
            registry.replace_scopes(dataset_id, value["scopes"])
            registry.update_dataset(
                dataset_id,
                status="ready_for_episode_selection",
                permanent_path=str(permanent),
                validation=value,
            )
        except Exception as error:
            registry.update_dataset(
                dataset_id,
                status="failed",
                error=f"{type(error).__name__}: {error}",
            )

    @app.post("/api/datasets", status_code=status.HTTP_202_ACCEPTED)
    def upload_dataset(
        background: BackgroundTasks,
        adapter_id: str = Form(...),
        bundle: UploadFile = File(...),
    ) -> dict[str, Any]:
        if adapter_id != "ai_village":
            raise HTTPException(status_code=400, detail="Only the ai_village adapter is supported.")
        if not bundle.filename or not bundle.filename.lower().endswith(".zip"):
            raise HTTPException(status_code=400, detail="The supported upload format is one ZIP file.")
        dataset = registry.create_dataset(adapter_id)
        try:
            staged = stage_upload(
                bundle.file,
                dataset_id=dataset["id"],
                uploads_root=layout.uploads_root,
                limits=settings.upload_limits,
            )
        except Exception as error:
            registry.update_dataset(
                dataset["id"],
                status="failed",
                error=f"{type(error).__name__}: {error}",
            )
            raise HTTPException(status_code=400, detail=str(error)) from error
        background.add_task(validate_staged, dataset["id"], adapter_id, staged)
        return _public_dataset(registry.get_dataset(dataset["id"]) or dataset)

    @app.get("/api/datasets/{dataset_id}")
    def get_dataset(dataset_id: str) -> dict[str, Any]:
        dataset = registry.get_dataset(dataset_id)
        if dataset is None:
            raise HTTPException(status_code=404, detail="Dataset not found.")
        return _public_dataset(dataset)

    @app.get("/api/datasets/{dataset_id}/scopes")
    def get_scopes(dataset_id: str) -> dict[str, Any]:
        dataset = registry.get_dataset(dataset_id)
        if dataset is None:
            raise HTTPException(status_code=404, detail="Dataset not found.")
        if dataset["status"] != "ready_for_episode_selection":
            raise HTTPException(status_code=409, detail="Dataset validation is not complete.")
        return {"dataset_id": dataset_id, "scopes": registry.list_scopes(dataset_id)}

    @app.post("/api/runs", status_code=status.HTTP_202_ACCEPTED)
    def create_run(request: RunRequest) -> dict[str, Any]:
        dataset = registry.get_dataset(request.dataset_id)
        if dataset is None:
            raise HTTPException(status_code=404, detail="Dataset not found.")
        if dataset["status"] != "ready_for_episode_selection":
            raise HTTPException(status_code=409, detail="Dataset is not ready for analysis.")
        scope = registry.get_scope(request.dataset_id, request.scope_id)
        if scope is None:
            raise HTTPException(status_code=404, detail="Investigation scope not found.")
        if not scope["runnable"]:
            raise HTTPException(status_code=409, detail=scope["blocking_reason"])
        run = registry.create_run(request.dataset_id, scope, run_root=layout.output_root)
        worker_manager.submit_deterministic(run["id"])
        return _public_run(registry.get_run(run["id"]) or run)

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, Any]:
        run = registry.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found.")
        return _public_run(run)

    @app.post("/api/runs/{run_id}/interpret", status_code=status.HTTP_202_ACCEPTED)
    def approve_interpretation(run_id: str) -> dict[str, Any]:
        run = registry.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found.")
        if run["status"] != "awaiting_interpretation_approval":
            raise HTTPException(status_code=409, detail="Run is not awaiting interpretation approval.")
        if worker_manager.busy:
            raise HTTPException(status_code=409, detail="The local analysis worker is busy; retry shortly.")
        registry.update_run(
            run_id,
            status="interpreting",
            phase="interpretation_approved",
            retryable=False,
            error=None,
            failure_kind=None,
        )
        try:
            worker_manager.submit_interpretation(run_id)
        except WorkerBusyError as error:
            registry.update_run(
                run_id,
                status="awaiting_interpretation_approval",
                phase="deterministic_analysis_complete",
            )
            raise HTTPException(status_code=409, detail=str(error)) from error
        return _public_run(registry.get_run(run_id) or run)

    @app.post("/api/runs/{run_id}/retry", status_code=status.HTTP_202_ACCEPTED)
    def retry_run(run_id: str) -> dict[str, Any]:
        try:
            mode = registry.prepare_retry(run_id)
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        if mode == "interpret":
            if worker_manager.busy:
                return _public_run(registry.get_run(run_id) or {})
            worker_manager.submit_interpretation(run_id)
        else:
            worker_manager.submit_deterministic(run_id)
        return _public_run(registry.get_run(run_id) or {})

    @app.get("/api/runs/{run_id}/view-model")
    def runtime_view_model(run_id: str):
        run = registry.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found.")
        if run["status"] != "completed" or not run.get("view_model_path"):
            raise HTTPException(status_code=409, detail="Runtime investigation is not complete.")
        path = Path(run["view_model_path"])
        if not path.is_file() or not path.is_relative_to(layout.output_root):
            raise HTTPException(status_code=500, detail="Completed view model is unavailable.")
        return FileResponse(path, media_type="application/json")

    @app.get("/api/runs/{run_id}/logs")
    def run_logs(run_id: str):
        run = registry.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found.")
        path = Path(run["log_path"])
        if not path.is_file():
            return PlainTextResponse("")
        size = path.stat().st_size
        with path.open("rb") as stream:
            stream.seek(max(0, size - settings.max_log_response_bytes))
            text = stream.read(settings.max_log_response_bytes).decode("utf-8", errors="replace")
        return PlainTextResponse(text)

    return app


app = create_app()
