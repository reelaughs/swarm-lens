from __future__ import annotations

import gzip
import json
import zipfile
from datetime import datetime, timedelta
from pathlib import Path


def _timestamp(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S.%f")


def write_jsonl_gzip(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wb") as stream:
        for row in rows:
            stream.write(json.dumps(row, separators=(",", ":")).encode() + b"\n")


def make_ai_village_raw(root: Path) -> Path:
    raw = root / "raw"
    raw.mkdir(parents=True)
    base = datetime(2026, 1, 1)
    agents = [
        {
            "id": f"agent-{index}",
            "name": f"Agent {index}",
            "model_string": "test-model",
            "village_id": "village-1",
            "created_at": _timestamp(base - timedelta(days=1)),
            "updated_at": _timestamp(base - timedelta(days=1)),
        }
        for index in range(1, 4)
    ]
    goals = [
        {
            "id": "goal-runnable",
            "village_id": "village-1",
            "goal": "Runnable episode",
            "start_time": _timestamp(base),
            "end_time": _timestamp(base + timedelta(hours=7)),
            "created_at": _timestamp(base),
            "updated_at": _timestamp(base),
        },
        {
            "id": "goal-underpowered",
            "village_id": "village-1",
            "goal": "Sparse episode",
            "start_time": _timestamp(base + timedelta(hours=7)),
            "end_time": _timestamp(base + timedelta(hours=8)),
            "created_at": _timestamp(base),
            "updated_at": _timestamp(base),
        },
        {
            "id": "goal-open",
            "village_id": "village-1",
            "goal": "Ongoing episode",
            "start_time": _timestamp(base + timedelta(hours=8)),
            "end_time": None,
            "created_at": _timestamp(base),
            "updated_at": _timestamp(base),
        },
    ]
    chats = [
        {
            "id": f"chat-{index}",
            "agent_speaker_id": f"agent-{index % 3 + 1}",
            "user_speaker_id": None,
            "speaker_type": "agent",
            "content": [
                "orbit galaxy",
                "repair protocol",
                "archive relay",
                "structure evidence",
                "coordinate signal",
            ][index % 5],
            "room_id": "room-1",
            "created_at": _timestamp(base + timedelta(minutes=2 + index)),
            "updated_at": _timestamp(base + timedelta(minutes=2 + index)),
            "has_been_approved": None,
        }
        for index in range(10)
    ]
    sessions = [
        {
            "id": f"session-{index}",
            "agent_id": f"agent-{index % 3 + 1}",
            "village_id": "village-1",
            "session_goal": [
                "inspect repair",
                "validate publish",
                "coordinate integrate",
                "test document",
                "deploy review",
            ][index % 5],
            "short_displayed_session_goal": f"Objective {index}",
            "created_at": _timestamp(base + timedelta(minutes=15 + index)),
            "updated_at": _timestamp(base + timedelta(minutes=15 + index)),
            "has_been_asked_to_stop": False,
        }
        for index in range(10)
    ]
    events = []
    event_index = 1
    # Twelve adjacent, activity-eligible 30-minute windows.
    for window in range(12):
        start = base + timedelta(minutes=window * 30 + 1)
        for offset in range(20):
            events.append(
                {
                    "id": f"event-{event_index}",
                    "event_index": event_index,
                    "data": {
                        "actionType": "WAIT",
                        "agentId": f"agent-{offset % 3 + 1}",
                    },
                    "village_id": "village-1",
                    "created_at": _timestamp(start + timedelta(seconds=offset)),
                    "updated_at": _timestamp(start + timedelta(seconds=offset)),
                }
            )
            event_index += 1

    write_jsonl_gzip(raw / "agents.jsonl.gz", agents)
    write_jsonl_gzip(raw / "village_goals.jsonl.gz", goals)
    write_jsonl_gzip(raw / "agent_goals.jsonl.gz", [])
    write_jsonl_gzip(raw / "chat_messages.jsonl.gz", chats)
    write_jsonl_gzip(raw / "computer_use_sessions.jsonl.gz", sessions)
    write_jsonl_gzip(raw / "events.jsonl.gz", events)
    (raw / "CHANGELOG.md").write_text("# Test changelog\n", encoding="utf-8")
    return raw


def zip_raw(raw: Path, destination: Path) -> Path:
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(raw.iterdir()):
            archive.write(path, path.name)
    return destination
