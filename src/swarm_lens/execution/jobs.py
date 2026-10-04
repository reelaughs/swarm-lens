"""Small SQLite registry for datasets and one-machine analysis jobs."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DATASET_STATES = {"uploaded", "validating", "ready_for_episode_selection", "failed"}
RUN_STATES = {
    "queued",
    "running",
    "awaiting_interpretation_approval",
    "interpreting",
    "packaging",
    "completed",
    "failed",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _decode(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    result = dict(row)
    for key in ("validation_json", "descriptor_json"):
        if key in result and result[key] is not None:
            result[key.removesuffix("_json")] = json.loads(result.pop(key))
    for key in ("retryable",):
        if key in result:
            result[key] = bool(result[key])
    return result


class JobRegistry:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS datasets (
                    id TEXT PRIMARY KEY,
                    adapter_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    permanent_path TEXT,
                    validation_json TEXT,
                    error TEXT
                );
                CREATE TABLE IF NOT EXISTS scopes (
                    dataset_id TEXT NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
                    scope_id TEXT NOT NULL,
                    descriptor_json TEXT NOT NULL,
                    PRIMARY KEY (dataset_id, scope_id)
                );
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    dataset_id TEXT NOT NULL REFERENCES datasets(id),
                    scope_id TEXT NOT NULL,
                    episode_slug TEXT NOT NULL,
                    status TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    retryable INTEGER NOT NULL DEFAULT 0,
                    failure_kind TEXT,
                    error TEXT,
                    worker_pid INTEGER,
                    view_model_path TEXT,
                    log_path TEXT NOT NULL
                );
                """
            )

    @staticmethod
    def new_id(prefix: str) -> str:
        # Compact 80-bit opaque IDs leave headroom for deep Windows audit paths.
        return f"{prefix}_{uuid.uuid4().hex[:20]}"

    def create_dataset(self, adapter_id: str) -> dict[str, Any]:
        dataset_id = self.new_id("d")
        now = _now()
        with self._lock, self._connect() as db:
            db.execute(
                "INSERT INTO datasets(id,adapter_id,status,created_at,updated_at) VALUES(?,?,?,?,?)",
                (dataset_id, adapter_id, "uploaded", now, now),
            )
        return self.get_dataset(dataset_id)  # type: ignore[return-value]

    def update_dataset(
        self,
        dataset_id: str,
        *,
        status: str,
        permanent_path: str | None = None,
        validation: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        if status not in DATASET_STATES:
            raise ValueError(f"invalid dataset state: {status}")
        with self._lock, self._connect() as db:
            cursor = db.execute(
                """UPDATE datasets SET status=?,updated_at=?,permanent_path=COALESCE(?,permanent_path),
                   validation_json=COALESCE(?,validation_json),error=? WHERE id=?""",
                (
                    status,
                    _now(),
                    permanent_path,
                    json.dumps(validation, ensure_ascii=False) if validation is not None else None,
                    error,
                    dataset_id,
                ),
            )
            if cursor.rowcount != 1:
                raise KeyError(dataset_id)

    def replace_scopes(self, dataset_id: str, scopes: list[dict[str, Any]]) -> None:
        with self._lock, self._connect() as db:
            db.execute("DELETE FROM scopes WHERE dataset_id=?", (dataset_id,))
            db.executemany(
                "INSERT INTO scopes(dataset_id,scope_id,descriptor_json) VALUES(?,?,?)",
                [
                    (dataset_id, scope["scope_id"], json.dumps(scope, ensure_ascii=False))
                    for scope in scopes
                ],
            )

    def get_dataset(self, dataset_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            return _decode(db.execute("SELECT * FROM datasets WHERE id=?", (dataset_id,)).fetchone())

    def list_scopes(self, dataset_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT descriptor_json FROM scopes WHERE dataset_id=? ORDER BY json_extract(descriptor_json,'$.start')",
                (dataset_id,),
            ).fetchall()
        return [json.loads(row["descriptor_json"]) for row in rows]

    def get_scope(self, dataset_id: str, scope_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT descriptor_json FROM scopes WHERE dataset_id=? AND scope_id=?",
                (dataset_id, scope_id),
            ).fetchone()
        return json.loads(row["descriptor_json"]) if row else None

    def create_run(self, dataset_id: str, scope: dict[str, Any], *, run_root: Path) -> dict[str, Any]:
        run_id = self.new_id("r")
        log_path = Path(run_root) / run_id / "worker.log"
        now = _now()
        with self._lock, self._connect() as db:
            db.execute(
                """INSERT INTO runs(
                    id,dataset_id,scope_id,episode_slug,status,phase,created_at,updated_at,log_path
                ) VALUES(?,?,?,?,?,?,?,?,?)""",
                (
                    run_id,
                    dataset_id,
                    scope["scope_id"],
                    scope["slug"],
                    "queued",
                    "deterministic_analysis_queued",
                    now,
                    now,
                    str(log_path),
                ),
            )
        return self.get_run(run_id)  # type: ignore[return-value]

    def update_run(self, run_id: str, **changes: Any) -> None:
        allowed = {
            "status",
            "phase",
            "retryable",
            "failure_kind",
            "error",
            "worker_pid",
            "view_model_path",
        }
        unknown = set(changes) - allowed
        if unknown:
            raise ValueError(f"unsupported run fields: {sorted(unknown)}")
        if "status" in changes and changes["status"] not in RUN_STATES:
            raise ValueError(f"invalid run state: {changes['status']}")
        if "retryable" in changes:
            changes["retryable"] = int(bool(changes["retryable"]))
        changes["updated_at"] = _now()
        assignments = ",".join(f"{key}=?" for key in changes)
        values = list(changes.values()) + [run_id]
        with self._lock, self._connect() as db:
            cursor = db.execute(f"UPDATE runs SET {assignments} WHERE id=?", values)
            if cursor.rowcount != 1:
                raise KeyError(run_id)

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            return _decode(db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone())

    def next_queued_run(self) -> dict[str, Any] | None:
        with self._connect() as db:
            return _decode(
                db.execute(
                    "SELECT * FROM runs WHERE status='queued' ORDER BY created_at LIMIT 1"
                ).fetchone()
            )

    def recover_interrupted_runs(self) -> int:
        """Mark work that cannot still own a worker after API startup as retryable."""

        with self._lock, self._connect() as db:
            cursor = db.execute(
                """UPDATE runs SET status='failed',phase='interrupted',retryable=1,
                   failure_kind='interrupted_worker',error='Worker was interrupted before completion.',
                   worker_pid=NULL,updated_at=?
                   WHERE status IN ('running','interpreting','packaging')""",
                (_now(),),
            )
            return cursor.rowcount

    def prepare_retry(self, run_id: str) -> str:
        run = self.get_run(run_id)
        if not run or run["status"] != "failed" or not run["retryable"]:
            raise ValueError("run is not retryable")
        mode = "interpret" if run.get("failure_kind") in {
            "interpretation_failure",
            "packaging_failure",
        } else "deterministic"
        self.update_run(
            run_id,
            status="queued",
            phase=f"{mode}_retry_queued",
            retryable=False,
            failure_kind=None,
            error=None,
            worker_pid=None,
        )
        return mode
