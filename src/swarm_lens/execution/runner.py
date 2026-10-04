"""Orchestrate existing pipeline functions inside dataset/run-specific roots."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import pyarrow.parquet as pq

from swarm_lens.datasets.ai_village import adapter_for
from swarm_lens.evidence_reconstruction import load_config as load_reconstruction_config
from swarm_lens.evidence_reconstruction import run_reconstruction
from swarm_lens.interpretation.config import load_config as load_interpretation_config
from swarm_lens.interpretation.evidence_bundle import canonical_json
from swarm_lens.interpretation.hypotheses import load_hypothesis_library
from swarm_lens.interpretation.openai_provider import OpenAIResponsesProvider
from swarm_lens.interpretation.pipeline import run_interpretation
from swarm_lens.turning_points import load_config as load_detector_config
from swarm_lens.turning_points import run_detection
from swarm_lens.turning_points.brief import export_candidate_brief
from swarm_lens.turning_points.context import export_candidate_context

from .jobs import JobRegistry


@dataclass(frozen=True)
class WorkspaceLayout:
    repository_root: Path
    uploads_root: Path
    processed_root: Path
    interim_root: Path
    output_root: Path

    @classmethod
    def under(
        cls, repository_root: Path, workspace_root: Path | None = None
    ) -> "WorkspaceLayout":
        root = Path(repository_root).resolve()
        storage = Path(workspace_root).resolve() if workspace_root is not None else root
        return cls(
            repository_root=root,
            uploads_root=storage / "data" / "uploads",
            processed_root=storage / "data" / "processed" / "d",
            interim_root=storage / "data" / "interim" / "d",
            output_root=storage / "outputs" / "runs",
        )

    def dataset_raw(self, dataset_id: str) -> Path:
        return self.uploads_root / dataset_id / "raw"

    def processed_episodes(self, dataset_id: str) -> Path:
        return self.processed_root / dataset_id / "episodes"

    def interim_episodes(self, dataset_id: str) -> Path:
        return self.interim_root / dataset_id

    def run_episodes(self, run_id: str) -> Path:
        return self.output_root / run_id / "episodes"

    def run_dir(self, run_id: str) -> Path:
        return self.output_root / run_id


def _load_presentation_module(repository_root: Path):
    path = repository_root / "scripts" / "build_frontend_view_model.py"
    spec = importlib.util.spec_from_file_location("swarm_lens_runtime_view_model", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load presentation adapter from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class PipelineRunner:
    def __init__(self, *, registry: JobRegistry, layout: WorkspaceLayout) -> None:
        self.registry = registry
        self.layout = layout

    def _log(self, run: dict[str, Any], message: str) -> None:
        path = Path(run["log_path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(message.rstrip() + "\n")

    def _phase(self, run_id: str, status: str, phase: str) -> dict[str, Any]:
        self.registry.update_run(
            run_id,
            status=status,
            phase=phase,
            worker_pid=os.getpid(),
            retryable=False,
            error=None,
            failure_kind=None,
        )
        run = self.registry.get_run(run_id)
        assert run is not None
        self._log(run, f"[{phase}]")
        return run

    def run_deterministic(self, run_id: str) -> None:
        run = self.registry.get_run(run_id)
        if run is None:
            raise KeyError(run_id)
        dataset = self.registry.get_dataset(run["dataset_id"])
        scope = self.registry.get_scope(run["dataset_id"], run["scope_id"])
        if not dataset or dataset["status"] != "ready_for_episode_selection":
            raise ValueError("dataset is not ready for analysis")
        if not scope or not scope["runnable"]:
            raise ValueError("selected investigation scope is not runnable")
        adapter = adapter_for(dataset["adapter_id"], repository_root=self.layout.repository_root)
        raw_dir = self.layout.dataset_raw(run["dataset_id"])
        processed_root = self.layout.processed_episodes(run["dataset_id"])
        interim_root = self.layout.interim_episodes(run["dataset_id"])
        output_root = self.layout.run_episodes(run_id)
        try:
            self._phase(run_id, "running", "canonicalizing")
            build = adapter.materialize_scope(
                raw_dir=raw_dir,
                scope_id=run["scope_id"],
                processed_root=processed_root,
                output_root=output_root,
            )
            if build.episode.slug != run["episode_slug"]:
                raise ValueError(
                    f"discovered/materialized episode slug mismatch: {run['episode_slug']} != {build.episode.slug}"
                )

            self._phase(run_id, "running", "detecting_behavioral_changes")
            detection = run_detection(
                canonical_path=build.parquet_path,
                episode_slug=build.episode.slug,
                config=load_detector_config(self.layout.repository_root / "configs" / "turning_points.toml"),
                interim_root=interim_root,
                output_root=output_root,
            )
            if detection.recommended_window_minutes is None or detection.candidate_count < 1:
                raise ValueError("the frozen detector produced no reliable candidate turning points")

            turning_points = output_root / build.episode.slug / "turning_points"
            context_inputs = adapter.contextual_inputs(raw_dir)
            self._phase(run_id, "running", "exporting_context")
            export_candidate_context(
                canonical_path=build.parquet_path,
                candidates_path=turning_points / "top_candidates.parquet",
                raw_dir=context_inputs["raw_dir"],
                changelog_path=context_inputs["changelog_path"],
                output_markdown=turning_points / "candidate_context.md",
                output_json=turning_points / "candidate_context.json",
            )

            self._phase(run_id, "running", "building_evidence_brief")
            resolved = json.loads(
                (turning_points / "resolved_configuration.json").read_text(encoding="utf-8")
            )
            cache_name = (
                f"{resolved['configuration_sha256'][:12]}-"
                f"{resolved['canonical_input_sha256'][:12]}"
            )
            detector_cache = interim_root / build.episode.slug / "turning_points" / cache_name
            export_candidate_brief(
                context_json=turning_points / "candidate_context.json",
                candidates_path=turning_points / "top_candidates.parquet",
                topic_features_path=detector_cache / "topic_features.parquet",
                output_markdown=turning_points / "candidate_brief.md",
                output_json=turning_points / "candidate_brief.json",
            )

            ranks = [
                int(row["rank"])
                for row in pq.read_table(turning_points / "top_candidates.parquet", columns=["rank"]).to_pylist()
            ]
            if sorted(ranks) != list(range(1, len(ranks) + 1)):
                raise ValueError(f"detector ranks are not contiguous: {sorted(ranks)}")
            self._phase(run_id, "running", "reconstructing_evidence")
            run_reconstruction(
                canonical_path=build.parquet_path,
                candidates_path=turning_points / "top_candidates.parquet",
                candidate_context_path=turning_points / "candidate_context.json",
                candidate_brief_path=turning_points / "candidate_brief.json",
                inactive_gaps_path=turning_points / "inactive_gaps.csv",
                stage2_resolved_config_path=turning_points / "resolved_configuration.json",
                stage2_cache_dir=detector_cache,
                config=load_reconstruction_config(
                    self.layout.repository_root / "configs" / "evidence_reconstruction.toml"
                ),
                candidate_ranks=ranks,
                episode_slug=build.episode.slug,
                interim_root=interim_root,
                output_root=output_root,
            )
            self.registry.update_run(
                run_id,
                status="awaiting_interpretation_approval",
                phase="deterministic_analysis_complete",
                worker_pid=None,
                retryable=False,
            )
            self._log(self.registry.get_run(run_id) or run, "[awaiting_interpretation_approval]")
        except Exception as error:
            self.registry.update_run(
                run_id,
                status="failed",
                phase="deterministic_analysis_failed",
                retryable=True,
                failure_kind="deterministic_analysis_failure",
                error=f"{type(error).__name__}: {error}",
                worker_pid=None,
            )
            self._log(self.registry.get_run(run_id) or run, f"FAILED: {type(error).__name__}: {error}")
            raise

    def run_interpretation_and_package(
        self,
        run_id: str,
        *,
        provider_factory: Callable[[Any], Any] = OpenAIResponsesProvider,
    ) -> None:
        run = self.registry.get_run(run_id)
        if run is None:
            raise KeyError(run_id)
        if run["status"] not in {"awaiting_interpretation_approval", "interpreting", "queued", "failed"}:
            raise ValueError(f"run cannot be interpreted from state {run['status']}")
        dataset_id = run["dataset_id"]
        slug = run["episode_slug"]
        output_root = self.layout.run_episodes(run_id)
        interim_root = self.layout.interim_episodes(dataset_id)
        episode_output = output_root / slug
        episode_interim = interim_root / slug
        stage3_path = (
            episode_output
            / "turning_points"
            / "evidence_reconstruction"
            / "evidence_reconstruction.json"
        )
        try:
            self._phase(run_id, "interpreting", "generating_analyst_interpretation")
            stage3 = json.loads(stage3_path.read_text(encoding="utf-8"))
            ranks = [int(item["rank"]) for item in stage3["candidates"]]
            config = load_interpretation_config(
                self.layout.repository_root / "configs" / "interpretation.toml"
            )
            library = load_hypothesis_library(
                self.layout.repository_root / "configs" / "social_process_hypotheses.toml",
                confidence_levels=config.interpretation.confidence_levels,
            )
            interpretation = run_interpretation(
                stage3_path=stage3_path,
                config=config,
                library=library,
                candidate_ranks=ranks,
                episode_slug=slug,
                system_prompt_path=self.layout.repository_root / "prompts" / "stage4_system_v1.txt",
                developer_prompt_path=self.layout.repository_root / "prompts" / "stage4_developer_v1.txt",
                interim_root=interim_root,
                output_root=output_root,
                force_regenerate=False,
                provider_factory=provider_factory,
            )
            if interpretation.validated_count != len(ranks):
                raise ValueError(
                    f"only {interpretation.validated_count} of {len(ranks)} interpretations validated"
                )

            self._phase(run_id, "packaging", "packaging_runtime_investigation")
            output = json.loads(interpretation.output_json.read_text(encoding="utf-8"))
            keys: dict[int, str] = {}
            for candidate in output["candidates"]:
                rank = int(candidate["behavioral_change_rank"])
                identity = candidate["cache_identity"]
                key = hashlib.sha256(canonical_json(identity).encode("utf-8")).hexdigest()[:24]
                expected = episode_interim / "interpretation" / key / f"candidate_{rank}"
                if not (expected / "validated_interpretation.json").is_file():
                    raise FileNotFoundError(f"validated interpretation cache missing for rank {rank}")
                keys[rank] = key
            if sorted(keys) != ranks:
                raise ValueError("interpretation cache identities do not cover every candidate rank")

            scope = self.registry.get_scope(dataset_id, run["scope_id"])
            assert scope is not None
            run_dir = self.layout.run_dir(run_id)
            manifest = run_dir / "runtime_artifacts.toml"
            lines = [
                'manifest_version = "1.0"',
                "",
                f'[episodes."{slug}"]',
                f'slug = {json.dumps(slug)}',
                f'expected_goal = {json.dumps(scope["title"], ensure_ascii=False)}',
                f"candidate_ranks = [{', '.join(str(rank) for rank in ranks)}]",
                "",
                f'[episodes."{slug}".stage4_cache_keys]',
            ]
            lines.extend(f'"{rank}" = "{keys[rank]}"' for rank in ranks)
            manifest.parent.mkdir(parents=True, exist_ok=True)
            manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")

            presentation = _load_presentation_module(self.layout.repository_root)
            view_model_path = run_dir / "presentation" / f"{slug}.json"
            canonical_path = self.layout.processed_episodes(dataset_id) / slug / "events.parquet"
            presentation.write_view_model(
                self.layout.repository_root,
                view_model_path,
                slug,
                manifest,
                canonical_path=canonical_path,
                episode_output_dir=episode_output,
                episode_interim_dir=episode_interim,
            )
            self.registry.update_run(
                run_id,
                status="completed",
                phase="completed",
                view_model_path=str(view_model_path),
                worker_pid=None,
                retryable=False,
            )
            self._log(self.registry.get_run(run_id) or run, "[completed]")
        except Exception as error:
            current = self.registry.get_run(run_id) or run
            packaging = current["status"] == "packaging"
            self.registry.update_run(
                run_id,
                status="failed",
                phase="presentation_packaging_failed" if packaging else "interpretation_failed",
                retryable=True,
                failure_kind="packaging_failure" if packaging else "interpretation_failure",
                error=f"{type(error).__name__}: {error}",
                worker_pid=None,
            )
            self._log(self.registry.get_run(run_id) or run, f"FAILED: {type(error).__name__}: {error}")
            raise
