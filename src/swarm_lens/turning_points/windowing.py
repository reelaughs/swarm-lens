"""UTC window construction and activity/gap diagnostics."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping

UTC = timezone.utc


@dataclass
class Window:
    index: int
    start: datetime
    end: datetime
    rows: list[Mapping[str, Any]] = field(default_factory=list)
    chat_rows: list[Mapping[str, Any]] = field(default_factory=list)
    agent_chat_rows: list[Mapping[str, Any]] = field(default_factory=list)
    session_rows: list[Mapping[str, Any]] = field(default_factory=list)
    event_rows: list[Mapping[str, Any]] = field(default_factory=list)
    agent_event_rows: list[Mapping[str, Any]] = field(default_factory=list)

    @property
    def distinct_agents(self) -> int:
        return len({row["agent_id"] for row in self.agent_event_rows if row.get("agent_id")})

    @property
    def active(self) -> bool:
        return bool(self.chat_rows or self.session_rows or self.event_rows)


def floor_utc(timestamp: datetime, minutes: int) -> datetime:
    if timestamp.tzinfo is None:
        raise ValueError("window timestamps must be timezone-aware")
    seconds = minutes * 60
    epoch = int(timestamp.timestamp())
    return datetime.fromtimestamp((epoch // seconds) * seconds, tz=UTC)


def build_windows(
    rows: Iterable[Mapping[str, Any]],
    episode_start: datetime,
    episode_end: datetime,
    minutes: int,
) -> list[Window]:
    if episode_end <= episode_start:
        raise ValueError("episode end must be after start")
    first = floor_utc(episode_start, minutes)
    seconds = minutes * 60
    count = math.ceil((episode_end - first).total_seconds() / seconds)
    windows = []
    for i in range(count):
        nominal_start = first + timedelta(minutes=i * minutes)
        nominal_end = first + timedelta(minutes=(i + 1) * minutes)
        windows.append(
            Window(
                index=i,
                start=max(nominal_start, episode_start),
                end=min(nominal_end, episode_end),
            )
        )
    for row in rows:
        timestamp = row["event_timestamp"]
        if timestamp < episode_start or timestamp >= episode_end:
            continue
        index = int((timestamp - first).total_seconds() // seconds)
        window = windows[index]
        window.rows.append(row)
        kind = row["event_kind"]
        if kind == "chat_message":
            window.chat_rows.append(row)
            if row.get("speaker_type") == "agent" and row.get("agent_id") and row.get("chat_content"):
                window.agent_chat_rows.append(row)
        elif kind == "computer_use_session_goal":
            window.session_rows.append(row)
        elif kind == "high_level_event":
            window.event_rows.append(row)
            if row.get("agent_id"):
                window.agent_event_rows.append(row)
    return windows


def inactive_gaps(windows: list[Window], minutes: int) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    start: Window | None = None
    previous: Window | None = None
    for window in windows + [None]:  # type: ignore[list-item]
        if window is not None and not window.active:
            start = start or window
            previous = window
            continue
        if start is not None and previous is not None:
            gap_windows = previous.index - start.index + 1
            duration_minutes = int((previous.end - start.start).total_seconds() / 60)
            gaps.append(
                {
                    "start": start.start,
                    "end": previous.end,
                    "windows": gap_windows,
                    "duration_minutes": duration_minutes,
                }
            )
        start = None
        previous = None
    return gaps


def eligible_window(window: Window, *, min_events: int, min_agents: int) -> bool:
    return len(window.event_rows) >= min_events and window.distinct_agents >= min_agents


def eligible_adjacent_pairs(
    windows: list[Window],
    *,
    min_events: int,
    min_agents: int,
) -> list[tuple[Window, Window]]:
    return [
        (before, after)
        for before, after in zip(windows, windows[1:])
        if eligible_window(before, min_events=min_events, min_agents=min_agents)
        and eligible_window(after, min_events=min_events, min_agents=min_agents)
    ]
