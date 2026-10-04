"""Tables, plots, and causal-neutral Markdown reporting."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pyarrow as pa
import pyarrow.parquet as pq

COMPONENTS = ("communication", "intention", "participation", "action_type")
COLORS = {
    "communication": "#2563eb",
    "intention": "#7c3aed",
    "participation": "#059669",
    "action_type": "#d97706",
    "aggregate": "#111827",
}


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_parquet(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(list(rows)), path, compression="zstd")


def plot_scores(output_dir: Path, rows_by_size: Mapping[int, Sequence[Mapping[str, Any]]]) -> list[Path]:
    paths: list[Path] = []
    for size, rows in rows_by_size.items():
        figure, axis = plt.subplots(figsize=(13, 6))
        for component in COMPONENTS:
            label = component.replace("_", " ")
            for run_index, run in enumerate(_contiguous_runs(rows, size)):
                axis.plot(
                    [row["transition_timestamp"] for row in run],
                    [row[f"{component}_z"] for row in run],
                    marker=".",
                    linewidth=1.2,
                    alpha=0.75,
                    label=label if run_index == 0 else None,
                    color=COLORS[component],
                )
        for run_index, run in enumerate(_contiguous_runs(rows, size)):
            axis.plot(
                [row["transition_timestamp"] for row in run],
                [row["aggregate_score"] for row in run],
                marker="o",
                markersize=3,
                linewidth=2.2,
                label="aggregate" if run_index == 0 else None,
                color=COLORS["aggregate"],
            )
        axis.axhline(0, color="#9ca3af", linewidth=0.8)
        axis.set_title(f"Population-level transition scores ({size}-minute windows)")
        axis.set_xlabel("Transition boundary (UTC)")
        axis.set_ylabel("Robust standardized score")
        axis.grid(alpha=0.2)
        axis.legend(ncol=5, fontsize=8)
        figure.autofmt_xdate()
        figure.tight_layout()
        path = output_dir / f"transition_scores_{size}m.png"
        figure.savefig(path, dpi=160)
        plt.close(figure)
        paths.append(path)
    return paths


def _contiguous_runs(rows: Sequence[Mapping[str, Any]], window_minutes: int) -> list[list[Mapping[str, Any]]]:
    runs: list[list[Mapping[str, Any]]] = []
    for row in rows:
        if not runs or (row["transition_timestamp"] - runs[-1][-1]["transition_timestamp"]).total_seconds() != window_minutes * 60:
            runs.append([row])
        else:
            runs[-1].append(row)
    return runs


def _fmt(value: Any, digits: int = 3) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _changes_markdown(changes: Sequence[Mapping[str, Any]]) -> str:
    if not changes:
        return "No eligible component distribution for this comparison."
    lines = ["| Item | Before | After | Δ |", "| --- | ---: | ---: | ---: |"]
    for item in changes:
        label = str(item["label"]).replace("|", "\\|")
        lines.append(f"| {label} | {_fmt(item['before'])} | {_fmt(item['after'])} | {_fmt(item['delta'])} |")
    return "\n".join(lines)


def render_report(
    *,
    episode_goal: str,
    episode_id: str,
    episode_interval: str,
    config_fingerprint: str,
    cache_hit: bool,
    diagnostic_summaries: Sequence[Mapping[str, Any]],
    recommended_size: int | None,
    candidates: Sequence[Mapping[str, Any]],
    standardization_by_size: Mapping[int, Mapping[str, Any]],
    topic_metadata: Mapping[str, Any],
    min_valid_comparisons: int,
    min_peak_separation_minutes: int,
) -> str:
    lines = [
        f"# Population-level turning points: {episode_goal}",
        "",
        "This calibration report ranks changes in collective behavior. It does not assign causal triggers or social-process labels.",
        "",
        "## Episode and detector",
        "",
        f"- Goal ID: `{episode_id}`",
        f"- Authoritative interval: `{episode_interval}` UTC",
        f"- Configuration fingerprint: `{config_fingerprint}`",
        f"- Topic cache reused: `{cache_hit}`",
        f"- Minimum valid comparisons for reliable standardization: `{min_valid_comparisons}`",
        f"- Minimum peak separation: `{min_peak_separation_minutes}` clock minutes",
        "- Participation and action-type signals are complementary views of the same high-level-event stream; they are not statistically independent measurements.",
        "",
        "## Windowing diagnostics",
        "",
        "| Window | Active / total | Overall-eligible | Adjacent comparisons | Valid aggregates | Inactive gaps | Inactive minutes | Max gap | Reliable |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in diagnostic_summaries:
        lines.append(
            f"| {row['window_size_minutes']}m | {row['active_windows']} / {row['total_windows']} | "
            f"{row['overall_eligible_windows']} | {row['overall_eligible_comparisons']} | "
            f"{row['valid_aggregate_comparisons']} | {row['inactive_gap_count']} | "
            f"{row['inactive_minutes']} | {row['max_inactive_gap_minutes']} | {row['reliable']} |"
        )
    lines.extend(["", f"Recommended initial window size: **{recommended_size} minutes**." if recommended_size else "No window size met the minimum-valid-comparisons requirement."])
    if recommended_size:
        lines.append("The recommendation rule chooses the smallest profiled window size with enough valid aggregate comparisons, preserving the highest supported temporal resolution.")

    lines.extend(["", "## Topic representations", ""])
    for modality in ("communication", "intention"):
        meta = topic_metadata[modality]
        lines.append(
            f"- **{modality.title()}**: {meta['documents_with_nonzero_topics']} usable documents, "
            f"{meta['vocabulary_size']} TF-IDF features, {meta['n_components']} NMF components, "
            f"reconstruction error {_fmt(meta['reconstruction_error'])}."
        )

    lines.extend(["", "## Standardization diagnostics", ""])
    for size, metadata in standardization_by_size.items():
        lines.append(f"### {size}-minute windows")
        lines.append("")
        lines.append("| Component | Valid raw divergences | Center | Scale | Method | Reliable |")
        lines.append("| --- | ---: | ---: | ---: | --- | --- |")
        for component in COMPONENTS:
            item = metadata[component]
            lines.append(
                f"| {component.replace('_', ' ')} | {item['valid_count']} | {_fmt(item['center'])} | "
                f"{_fmt(item['scale'])} | {item['scale_method'] or 'not standardized'} | {item['reliable']} |"
            )
        lines.append("")

    lines.extend(["## Top candidate turning points", ""])
    if not candidates:
        lines.append("No reliable peaks were available under the configured rules.")
    for candidate in candidates:
        lines.extend(
            [
                f"### {candidate['rank']}. {candidate['transition_timestamp'].isoformat()}",
                "",
                f"- Aggregate score: **{_fmt(candidate['aggregate_score'])}**",
                f"- Contributing components ({candidate['contributing_component_count']}): `{candidate['contributing_components']}`",
                f"- Before/after high-level events: {candidate['before_event_count']} → {candidate['after_event_count']}",
                f"- Before/after agent chats: {candidate['before_agent_chat_count']} → {candidate['after_agent_chat_count']}",
                f"- Before/after session goals: {candidate['before_session_count']} → {candidate['after_session_count']}",
                f"- Raw JS divergences: communication {_fmt(candidate['communication_js'])}, intention {_fmt(candidate['intention_js'])}, participation {_fmt(candidate['participation_js'])}, action type {_fmt(candidate['action_type_js'])}",
                f"- Standardized components: communication {_fmt(candidate['communication_z'])}, intention {_fmt(candidate['intention_z'])}, participation {_fmt(candidate['participation_z'])}, action type {_fmt(candidate['action_type_z'])}",
                "",
            ]
        )
        for component, title in (
            ("communication", "Communication-workstream changes"),
            ("intention", "Action/intention-workstream changes"),
            ("participation", "Agent-participation changes"),
            ("action_type", "High-level action-type changes"),
        ):
            lines.extend([f"#### {title}", "", _changes_markdown(candidate[f"{component}_changes"]), ""])

    lines.extend(
        [
            "## Interpretation boundary",
            "",
            "The detector identifies distributional discontinuities only. This report intentionally does not infer what caused a peak, classify a social process, or use an LLM to interpret the underlying records. Candidate evidence IDs are provided separately for later retrieval.",
            "",
        ]
    )
    return "\n".join(lines)
