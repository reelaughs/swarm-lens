"""One-concurrent-subprocess manager for local SwarmLens jobs."""

from __future__ import annotations

import subprocess
import sys
import threading
from pathlib import Path

from .jobs import JobRegistry


class WorkerBusyError(RuntimeError):
    pass


class WorkerManager:
    def __init__(
        self, *, repository_root: Path, registry: JobRegistry, workspace_root: Path | None = None
    ) -> None:
        self.repository_root = Path(repository_root).resolve()
        self.workspace_root = (
            Path(workspace_root).resolve() if workspace_root is not None else self.repository_root
        )
        self.registry = registry
        self._lock = threading.RLock()
        self._process: subprocess.Popen[str] | None = None
        self._active_run_id: str | None = None

    @property
    def busy(self) -> bool:
        with self._lock:
            return self._process is not None and self._process.poll() is None

    def start(self) -> None:
        self.registry.recover_interrupted_runs()
        self._kick_next()

    def submit_deterministic(self, run_id: str) -> None:
        # The registry row is already queued. If another job owns the single
        # slot, this job remains durably queued and is started by the watcher.
        self._kick_next()

    def submit_interpretation(self, run_id: str) -> None:
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                raise WorkerBusyError("the local analysis worker is busy")
            self._spawn(run_id, "interpret")

    def _kick_next(self) -> None:
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                return
            queued = self.registry.next_queued_run()
            if queued is not None:
                mode = "interpret" if "interpret" in queued["phase"] else "deterministic"
                self._spawn(queued["id"], mode)

    def _spawn(self, run_id: str, mode: str) -> None:
        run = self.registry.get_run(run_id)
        if run is None:
            raise KeyError(run_id)
        log_path = Path(run["log_path"])
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log = log_path.open("a", encoding="utf-8")
        command = [
            sys.executable,
            str(self.repository_root / "scripts" / "run_analysis_job.py"),
            "--repository-root",
            str(self.repository_root),
            "--registry",
            str(self.registry.path),
            "--workspace-root",
            str(self.workspace_root),
            "--run-id",
            run_id,
            "--mode",
            mode,
        ]
        try:
            process = subprocess.Popen(
                command,
                cwd=self.repository_root,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
                shell=False,
            )
        except Exception:
            log.close()
            raise
        self._process = process
        self._active_run_id = run_id
        self.registry.update_run(run_id, worker_pid=process.pid)
        watcher = threading.Thread(
            target=self._watch,
            args=(run_id, process, log),
            daemon=True,
            name=f"swarmlens-{run_id}",
        )
        watcher.start()

    def _watch(
        self,
        run_id: str,
        process: subprocess.Popen[str],
        log,
    ) -> None:
        return_code = process.wait()
        log.close()
        with self._lock:
            current = self.registry.get_run(run_id)
            if current and current["status"] in {"queued", "running", "interpreting", "packaging"}:
                self.registry.update_run(
                    run_id,
                    status="failed",
                    phase="worker_process_failed",
                    retryable=True,
                    failure_kind="worker_exit",
                    error=f"Worker exited with code {return_code} before recording a terminal state.",
                    worker_pid=None,
                )
            self._process = None
            self._active_run_id = None
        self._kick_next()
