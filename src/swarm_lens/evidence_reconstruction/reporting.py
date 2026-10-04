"""Compact Markdown rendering for structured Stage 3 evidence."""

from __future__ import annotations

from typing import Any, Mapping


def _escape(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", "<br>")


def _excerpt(value: Any, limit: int = 360) -> str:
    if value is None:
        return ""
    compact = str(value).replace("\r", " ").replace("\n", " ")
    return compact if len(compact) <= limit else compact[: limit - 1] + "…"


def _ids(provenance: list[Mapping[str, Any]]) -> str:
    return "<br>".join(f"`{row['canonical_event_id']}` / `{row['source_row_id']}`" for row in provenance)


def render_markdown(result: Mapping[str, Any]) -> str:
    metadata = result["metadata"]
    lines = [
        f"# Evidence reconstruction: {metadata['episode_goal']}",
        "",
        "This deterministic Stage 3 output reconstructs observable sequences and structure. It does not assign social-process labels, importance, intent, or causation.",
        "",
        f"- Stage 3 configuration: `{metadata['configuration_sha256']}`",
        f"- Semantic method: `{metadata['semantic_method']}`",
        f"- Candidate ranks: `{', '.join(str(value) for value in metadata['candidate_ranks'])}`",
        "",
    ]
    for candidate in result["candidates"]:
        lines.extend(
            [
                f"## Candidate {candidate['rank']}: {candidate['turning_point_timestamp']}",
                "",
                f"- Behavioral-change rank: **{candidate['rank']}**; aggregate Stage 2 score: **{candidate['aggregate_score']:.3f}**",
                f"- Effective coverage: baseline `{candidate['windows']['coverage_minutes']['baseline']:.1f}` min; antecedent `{candidate['windows']['coverage_minutes']['antecedent']:.1f}` min; follow-up `{candidate['windows']['coverage_minutes']['followup']:.1f}` min",
                f"- External-context flags: `{', '.join(candidate['external_context']['flags']) or 'none'}`",
                f"- Full forensic packet: [{candidate['full_context_reference']}]({candidate['full_context_reference']})",
                "",
                "### Stage 2 signal and deterministic change description",
                "",
            ]
        )
        lines.extend(f"- {value}" for value in candidate["deterministic_change_description"])
        lines.extend(["", "| Component | JS divergence | Standardized | Eligible |", "| --- | ---: | ---: | --- |"])
        for name, values in candidate["detector_component_scores"].items():
            js = "" if values["js_divergence"] is None else f"{values['js_divergence']:.3f}"
            z = "" if values["standardized_score"] is None else f"{values['standardized_score']:.3f}"
            lines.append(f"| {name.replace('_', ' ')} | {js} | {z} | {values['eligible']} |")

        lines.extend(["", "### Semantic-threshold diagnostics", "", "| Directed source pair | Threshold | Method | Background-pair denominator |", "| --- | ---: | --- | ---: |"])
        for pair, threshold in candidate["semantic_thresholds"].items():
            denominator = threshold.get("source_pair_background_pair_count", threshold.get("pair_count", 0))
            lines.append(f"| `{pair}` | {threshold['value']:.3f} | `{threshold['method']}` | {denominator} |")

        lines.extend(
            [
                "",
                "### Ranked preceding events",
                "",
                f"The aggregate-score reference is provisional (`{candidate['provisional_aggregate_score_reference']['threshold']:.2f}`) and does not establish antecedent status. All top-ranked evidence remains visible regardless of that reference.",
                "",
                "| Rank | Evidence label | Antecedent support | Time | Agent | Source | Aggregate | N / P / U / A / R | Evidence excerpt | Provenance |",
                "| ---: | --- | --- | --- | --- | --- | ---: | --- | --- | --- |",
            ]
        )
        for event in candidate["ranked_preceding_events"]:
            scores = event["score_components"]
            score_text = " / ".join("—" if scores[key] is None else f"{scores[key]:.2f}" for key in ("novelty", "proximity", "distinct_agent_uptake", "detector_alignment", "persistence"))
            aggregate = "" if event["aggregate_score"] is None else f"{event['aggregate_score']:.3f}"
            lines.append(
                f"| {event['preceding_event_rank']} | `{event['evidence_label']}` | `{event['antecedent_support']}` | {_escape(event['timestamp'])} | {_escape(event['agent_name'])} | "
                f"{event['source_type']} | {aggregate} | {score_text} | {_escape(_excerpt(event['text']))} | {_ids(event['provenance'])} |"
            )

        lines.extend(["", "### Uptake and behavioral follow-through", ""])
        for event in candidate["ranked_preceding_events"]:
            uptake = event["uptake"]
            follow = event["behavioral_follow_through"]
            lines.extend(
                [
                    f"#### Ranked preceding evidence {event['preceding_event_rank']} — support `{event['antecedent_support']}`",
                    "",
                    f"- Semantic matches: **{uptake['matching_item_count']} / {uptake['eligible_later_text_item_count']}** eligible later text items; distinct matching agents: **{uptake['matching_agents_over_active_agents']}** active agents.",
                    f"- Agent-level follow-through: `{follow['classification']}`; qualifying agents / semantic-uptake agents: **{follow['follow_through_agents_over_semantic_uptake_agents']}**.",
                    f"- Population-level detector alignment: `{event['population_level_alignment']['score']}`. This is reported separately and does not establish follow-through.",
                    f"- Persistence: **{event['persistence']['presence_windows']} / {event['persistence']['eligible_windows']}** windows; `{event['persistence']['category']}`.",
                    "",
                ]
            )
            if uptake["highest_scoring_matches"]:
                lines.extend(["| Similarity | Source pair | Time | Agent | Evidence excerpt | Provenance |", "| ---: | --- | --- | --- | --- | --- |"])
                display_limit = metadata["configuration"]["semantics"]["max_markdown_matches_per_preceding_event"]
                for match in uptake["highest_scoring_matches"][:display_limit]:
                    lines.append(
                        f"| {match['similarity']:.3f} | `{match['source_type_pair']}` | {_escape(match['timestamp'])} | {_escape(match['agent_name'])} | "
                        f"{_escape(_excerpt(match['text'], 240))} | {_ids(match['provenance'])} |"
                    )
                lines.append("")

        lines.extend(["### Chronological evidence sequence", "", "| Time | Phase | Agent | Source | Selection basis | Evidence excerpt | Provenance |", "| --- | --- | --- | --- | --- | --- | --- |"])
        for item in candidate["chronological_evidence_sequence"]:
            lines.append(
                f"| {_escape(item['timestamp'])} | {item['phase']} | {_escape(item['agent_name'])} | {item['source_type']} | "
                f"{_escape('; '.join(item['selection_reasons']))} | {_escape(_excerpt(item['text'], 280))} | {_ids(item['provenance'])} |"
            )

        structure = candidate["actor_and_structure"]
        lines.extend(["", "### Actor and structural observations", ""])
        for phase in ("antecedent", "followup"):
            value = structure[phase]
            concentration = value["concentration"]
            coactivity = value["co_activity"]
            lines.append(
                f"- **{phase}:** {concentration['distinct_active_agents']} distinct agents across {value['active_window_count']} active windows; "
                f"HHI `{concentration['hhi']}`; recurring same-window pairs **{coactivity['recurring_same_window_pair_count']} / {coactivity['eligible_agent_pairs']}** eligible pairs; "
                f"recurring same-room pairs `{coactivity['recurring_same_room_pair_count']}`."
            )
        lines.extend(
            [
                "",
                "Same-window co-activity is retained only as an activity-density/context measure. Same-room overlap is reported separately. Neither is relational evidence or independently supports later social-process interpretation.",
                "",
                f"- Explicit-address edges: **{candidate['explicit_address_relationships']['explicit_address_edge_count']}**.",
                "",
                "### Role/task asymmetry and persistence",
                "",
            ]
        )
        for modality, values in candidate["role_task_asymmetry"].items():
            before = values["antecedent"]
            after = values["followup"]
            persistent = sum(row["persistent_specialization"] for row in after["agents"])
            lines.append(
                f"- **{modality}:** qualified agents before/after `{before['agent_count_qualified']}/{after['agent_count_qualified']}`; "
                f"eligible agent-pair denominators `{before['eligible_agent_pairs']}/{after['eligible_agent_pairs']}`; agents with persistent same dominant activity after the boundary: `{persistent}`."
            )

        lines.extend(["", "### External context", ""])
        if candidate["external_context"]["events"]:
            for item in candidate["external_context"]["events"]:
                lines.append(f"- `{item['type']}` at `{item['time_or_date']}`: {_escape(item['description'])} (`{item['provenance']}`)")
        else:
            lines.append("- No inherited roster, goal-boundary, or dated-scaffolding event was present in the Stage 2.5 brief.")
        lines.extend(["", "### Null findings and caveats", ""])
        if candidate["null_findings"]:
            lines.extend(f"- {value}" for value in candidate["null_findings"])
        else:
            lines.append("- No configured null condition was met; this does not establish a coherent social process.")
        lines.extend(f"- Caveat: {value}" for value in candidate["caveats"])
        lines.append("")
    return "\n".join(lines)
