"""The one currently supported raw-data adapter: an AI Village export."""

from __future__ import annotations

import hashlib
from bisect import bisect_right
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from swarm_lens.ingestion import (
    IngestionError,
    build_episode,
    iter_raw_rows,
    parse_timestamp,
    safe_slug,
)
from swarm_lens.turning_points.config import TurningPointConfig, load_config
from swarm_lens.turning_points.topics import topic_vocabulary_size

from .base import DatasetInspection, ScopeDescriptor
from .secure_upload import REQUIRED_MEMBERS


class AIVillageAdapter:
    adapter_id = "ai_village"

    def __init__(self, detector_config_path: Path) -> None:
        self.detector_config_path = Path(detector_config_path)
        self.detector_config: TurningPointConfig = load_config(self.detector_config_path)

    def _fingerprint(self, raw_dir: Path) -> str:
        digest = hashlib.sha256()
        for name in sorted(REQUIRED_MEMBERS):
            path = raw_dir / name
            digest.update(name.encode("utf-8"))
            with path.open("rb") as stream:
                while block := stream.read(1024 * 1024):
                    digest.update(block)
        return digest.hexdigest()

    @staticmethod
    def _goal_for_time(
        timestamp: datetime,
        goals: list[dict[str, Any]],
        starts: list[datetime],
    ) -> dict[str, Any] | None:
        index = bisect_right(starts, timestamp) - 1
        if index < 0:
            return None
        goal = goals[index]
        return goal if goal["end"] is None or timestamp < goal["end"] else None

    def inspect(self, raw_dir: Path) -> DatasetInspection:
        raw_dir = Path(raw_dir)
        missing = [name for name in REQUIRED_MEMBERS if not (raw_dir / name).is_file()]
        if missing:
            raise IngestionError(f"AI Village bundle is missing required files: {sorted(missing)}")

        raw_goals = list(iter_raw_rows(raw_dir, "village_goals"))
        if not raw_goals:
            raise IngestionError("village_goals contains no investigation scopes")
        goal_ids: set[str] = set()
        goals: list[dict[str, Any]] = []
        village_ids = {str(row.record["village_id"]) for row in raw_goals}
        if len(village_ids) != 1:
            raise IngestionError(
                "multi-village exports are not supported because chat rows cannot be disambiguated safely"
            )
        village_id = next(iter(village_ids))
        for row in raw_goals:
            record = row.record
            if record["id"] in goal_ids:
                raise IngestionError(f"duplicate village_goals.id: {record['id']}")
            goal_ids.add(record["id"])
            start = parse_timestamp(record["start_time"], field="village_goals.start_time")
            end = parse_timestamp(record["end_time"], field="village_goals.end_time", allow_none=True)
            assert start is not None
            if end is not None and end <= start:
                raise IngestionError(f"goal {record['id']} has a non-positive interval")
            goals.append({"record": record, "start": start, "end": end})
        goals.sort(key=lambda item: (item["start"], item["record"]["id"]))
        for previous, current in zip(goals, goals[1:]):
            if previous["end"] is None or current["start"] < previous["end"]:
                raise IngestionError("overlapping village-goal intervals are not supported")
        starts = [item["start"] for item in goals]
        slug_ids: dict[str, set[str]] = defaultdict(set)
        for item in goals:
            slug_ids[safe_slug(item["record"]["goal"])].add(item["record"]["id"])

        counts: Counter[str] = Counter(village_goals=len(raw_goals))
        agents: dict[str, dict[str, Any]] = {}
        for row in iter_raw_rows(raw_dir, "agents"):
            counts["agents"] += 1
            record = row.record
            if record["id"] in agents:
                raise IngestionError(f"duplicate agents.id: {record['id']}")
            if record["village_id"] != village_id:
                raise IngestionError("multi-village agent rows are not supported")
            agents[record["id"]] = record

        seen_agent_goals: set[str] = set()
        for row in iter_raw_rows(raw_dir, "agent_goals"):
            counts["agent_goals"] += 1
            record = row.record
            if record["id"] in seen_agent_goals:
                raise IngestionError(f"duplicate agent_goals.id: {record['id']}")
            seen_agent_goals.add(record["id"])
            if record["agent_id"] not in agents:
                raise IngestionError(f"agent goal references missing agent {record['agent_id']}")
            start = parse_timestamp(
                record["start_time"], field="agent_goals.start_time", allow_none=True
            )
            end = parse_timestamp(
                record["end_time"], field="agent_goals.end_time", allow_none=True
            )
            if start is not None and end is not None and end <= start:
                raise IngestionError(f"agent goal {record['id']} has a non-positive interval")

        metrics: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "communication_documents": 0,
                "intention_documents": 0,
                "communication_texts": [],
                "intention_texts": [],
                "high_level_events": 0,
                "agents": set(),
                "window_events": defaultdict(lambda: defaultdict(int)),
                "window_agents": defaultdict(lambda: defaultdict(set)),
            }
        )
        seen_chat: set[str] = set()
        for row in iter_raw_rows(raw_dir, "chat_messages"):
            counts["chat_messages"] += 1
            record = row.record
            if record["id"] in seen_chat:
                raise IngestionError(f"duplicate chat_messages.id: {record['id']}")
            seen_chat.add(record["id"])
            timestamp = parse_timestamp(record["created_at"], field="chat_messages.created_at")
            assert timestamp is not None
            goal = self._goal_for_time(timestamp, goals, starts)
            if record["speaker_type"] not in {"agent", "user"}:
                raise IngestionError(f"chat message {record['id']} has unknown speaker_type")
            agent_id = record.get("agent_speaker_id")
            if agent_id is not None and agent_id not in agents:
                raise IngestionError(f"chat message references missing agent {agent_id}")
            if goal and record["speaker_type"] == "agent" and str(record.get("content") or "").strip():
                metrics[goal["record"]["id"]]["communication_documents"] += 1
                metrics[goal["record"]["id"]]["communication_texts"].append(record["content"])

        seen_sessions: set[str] = set()
        for row in iter_raw_rows(raw_dir, "computer_use_sessions"):
            counts["computer_use_sessions"] += 1
            record = row.record
            if record["id"] in seen_sessions:
                raise IngestionError(f"duplicate computer_use_sessions.id: {record['id']}")
            seen_sessions.add(record["id"])
            if record["village_id"] != village_id:
                raise IngestionError("multi-village computer-use sessions are not supported")
            if record["agent_id"] not in agents:
                raise IngestionError(f"computer-use session references missing agent {record['agent_id']}")
            timestamp = parse_timestamp(record["created_at"], field="computer_use_sessions.created_at")
            assert timestamp is not None
            goal = self._goal_for_time(timestamp, goals, starts)
            if goal and str(record.get("session_goal") or "").strip():
                metrics[goal["record"]["id"]]["intention_documents"] += 1
                metrics[goal["record"]["id"]]["intention_texts"].append(record["session_goal"])

        seen_events: set[str] = set()
        seen_indexes: set[int] = set()
        detector = self.detector_config.detector
        for row in iter_raw_rows(raw_dir, "events"):
            counts["events"] += 1
            record = row.record
            if record["id"] in seen_events:
                raise IngestionError(f"duplicate events.id: {record['id']}")
            seen_events.add(record["id"])
            index = record["event_index"]
            if not isinstance(index, int) or isinstance(index, bool) or index in seen_indexes:
                raise IngestionError(f"invalid or duplicate events.event_index: {index!r}")
            seen_indexes.add(index)
            if record["village_id"] != village_id:
                raise IngestionError("multi-village event rows are not supported")
            data = record["data"]
            if not isinstance(data, dict) or not isinstance(data.get("actionType"), str):
                raise IngestionError(f"event {record['id']} has invalid data/actionType")
            timestamp = parse_timestamp(record["created_at"], field="events.created_at")
            assert timestamp is not None
            goal = self._goal_for_time(timestamp, goals, starts)
            if not goal:
                continue
            agent_id = data.get("speakerId") if data["actionType"] == "AGENT_TALK" else data.get("agentId")
            if agent_id is not None and agent_id not in agents:
                raise IngestionError(f"event references missing agent {agent_id}")
            goal_id = goal["record"]["id"]
            info = metrics[goal_id]
            info["high_level_events"] += 1
            if agent_id:
                info["agents"].add(agent_id)
            for minutes in detector.window_sizes_minutes:
                window = int(timestamp.timestamp() // (minutes * 60))
                info["window_events"][minutes][window] += 1
                if agent_id:
                    info["window_agents"][minutes][window].add(agent_id)

        components = max(
            self.detector_config.communication_model.n_components,
            self.detector_config.intention_model.n_components,
        )
        scopes: list[ScopeDescriptor] = []
        for goal in goals:
            record = goal["record"]
            info = metrics[record["id"]]
            blockers: list[str] = []
            warnings: list[str] = []
            if goal["end"] is None:
                blockers.append("The authoritative episode interval is still open.")
            if info["communication_documents"] < components:
                blockers.append(
                    f"Only {info['communication_documents']} usable agent chat documents are available; "
                    f"the frozen communication model requires at least {components}."
                )
            if info["intention_documents"] < components:
                blockers.append(
                    f"Only {info['intention_documents']} usable session-goal documents are available; "
                    f"the frozen intention model requires at least {components}."
                )
            if info["communication_documents"] >= components:
                vocabulary = topic_vocabulary_size(
                    info["communication_texts"], self.detector_config.communication_model
                )
                if vocabulary < self.detector_config.communication_model.n_components:
                    blockers.append(
                        f"The usable communication vocabulary has only {vocabulary} features; the "
                        f"frozen model requires at least {self.detector_config.communication_model.n_components}."
                    )
            if info["intention_documents"] >= components:
                vocabulary = topic_vocabulary_size(
                    info["intention_texts"], self.detector_config.intention_model
                )
                if vocabulary < self.detector_config.intention_model.n_components:
                    blockers.append(
                        f"The usable intention vocabulary has only {vocabulary} features; the frozen "
                        f"model requires at least {self.detector_config.intention_model.n_components}."
                    )
            eligible_comparisons: dict[int, int] = {}
            for minutes in detector.window_sizes_minutes:
                eligible_windows = sorted(
                    window
                    for window, count in info["window_events"][minutes].items()
                    if count >= detector.overall_min_high_level_events
                    and len(info["window_agents"][minutes][window])
                    >= detector.overall_min_distinct_agents
                )
                eligible_comparisons[minutes] = sum(
                    right == left + 1 for left, right in zip(eligible_windows, eligible_windows[1:])
                )
            best_comparisons = max(eligible_comparisons.values(), default=0)
            if best_comparisons < detector.min_valid_comparisons:
                blockers.append(
                    f"At most {best_comparisons} clearly activity-eligible adjacent comparisons are "
                    f"available across the frozen window sizes; the detector requires at least "
                    f"{detector.min_valid_comparisons}."
                )
            base_slug = safe_slug(record["goal"])
            slug = (
                base_slug
                if len(slug_ids[base_slug]) == 1
                else f"{base_slug}-{record['id'][:8]}"
            )
            scopes.append(
                ScopeDescriptor(
                    scope_id=record["id"],
                    title=record["goal"],
                    start=goal["start"].isoformat(),
                    end=goal["end"].isoformat() if goal["end"] else None,
                    slug=slug,
                    runnable=not blockers,
                    warnings=tuple(warnings),
                    blocking_reason=" ".join(blockers) or None,
                )
            )
        return DatasetInspection(
            adapter_id=self.adapter_id,
            dataset_fingerprint=self._fingerprint(raw_dir),
            village_id=village_id,
            source_counts=dict(counts),
            scopes=tuple(scopes),
        )

    def materialize_scope(
        self,
        *,
        raw_dir: Path,
        scope_id: str,
        processed_root: Path,
        output_root: Path,
    ):
        return build_episode(
            raw_dir=raw_dir,
            processed_root=processed_root,
            output_root=output_root,
            goal_id=scope_id,
        )

    def contextual_inputs(self, raw_dir: Path) -> dict[str, Path]:
        raw_dir = Path(raw_dir)
        return {"raw_dir": raw_dir, "changelog_path": raw_dir / "CHANGELOG.md"}


def adapter_for(adapter_id: str, *, repository_root: Path) -> AIVillageAdapter:
    if adapter_id != AIVillageAdapter.adapter_id:
        raise ValueError(f"unsupported dataset adapter: {adapter_id!r}")
    return AIVillageAdapter(Path(repository_root) / "configs" / "turning_points.toml")
