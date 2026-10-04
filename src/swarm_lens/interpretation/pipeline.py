"""End-to-end constrained Stage 4 interpretation pipeline."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .config import InterpretationConfig
from .evidence_bundle import build_evidence_bundle, canonical_json
from .hypotheses import HypothesisLibrary
from .openai_provider import OpenAIResponsesProvider, build_responses_request
from .prompts import build_instructions, build_user_input, load_prompt
from .provider import InterpretationProvider, ProviderAccessError
from .reporting import render_markdown
from .schemas import response_json_schema
from .validation import validate_interpretation


@dataclass(frozen=True)
class InterpretationRunResult:
    output_json: Path
    output_markdown: Path
    candidate_count: int
    validated_count: int
    cache_reused_count: int


@dataclass(frozen=True)
class RequestReconstructionResult:
    request_paths: tuple[Path, ...]
    candidate_count: int


def _hash_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")


def _next_generation_dir(candidate_cache_dir: Path) -> Path:
    generations = candidate_cache_dir / "generations"
    existing = sorted(generations.glob("generation_*")) if generations.is_dir() else []
    generation = generations / f"generation_{len(existing) + 1:03d}"
    generation.mkdir(parents=True, exist_ok=False)
    return generation


def _model_response_metadata(response: Any, validation_attempt: int) -> dict[str, Any]:
    return {
        "response_id": response.response_id,
        "model": response.model,
        "status": response.status,
        "usage": response.usage,
        "validation_attempt": validation_attempt,
    }


def reconstruct_interpretation_requests(
    *,
    stage3_path: Path,
    config: InterpretationConfig,
    library: HypothesisLibrary,
    candidate_ranks: Sequence[int],
    episode_slug: str,
    system_prompt_path: Path,
    developer_prompt_path: Path,
    interim_root: Path,
) -> RequestReconstructionResult:
    """Persist exact secret-free request previews without constructing a provider."""

    ranks = tuple(sorted(set(int(value) for value in candidate_ranks)))
    if not ranks:
        raise ValueError("at least one candidate rank is required")
    stage3 = json.loads(Path(stage3_path).read_text(encoding="utf-8"))
    candidates_by_rank = {int(value["rank"]): value for value in stage3["candidates"]}
    missing = sorted(set(ranks) - set(candidates_by_rank))
    if missing:
        raise ValueError(f"candidate ranks absent from Stage 3 output: {missing}")
    instructions = build_instructions(load_prompt(system_prompt_path), load_prompt(developer_prompt_path))
    schema = response_json_schema()
    episode_metadata = stage3["metadata"]
    reconstruction_identity = {
        "stage3_sha256": _hash_file(stage3_path),
        "configuration_sha256": config.fingerprint,
        "hypothesis_library_sha256": library.fingerprint,
        "system_prompt_sha256": _hash_file(system_prompt_path),
        "developer_prompt_sha256": _hash_file(developer_prompt_path),
        "response_schema_sha256": _hash_bytes(canonical_json(schema).encode("utf-8")),
    }
    preview_key = _hash_bytes(canonical_json(reconstruction_identity).encode("utf-8"))[:24]
    request_paths: list[Path] = []
    for rank in ranks:
        bundle = build_evidence_bundle(
            candidates_by_rank[rank], episode_metadata=episode_metadata, library=library, config=config.evidence
        )
        user_input = build_user_input(bundle)
        request = build_responses_request(config.provider, instructions=instructions, user_input=user_input, schema=schema)
        preview_dir = Path(interim_root) / episode_slug / "interpretation" / "request_previews" / preview_key / f"candidate_{rank}"
        _write_json(preview_dir / "input_evidence_bundle.json", bundle)
        _write_json(
            preview_dir / "request_identity.json",
            {**reconstruction_identity, "candidate_rank": rank, "evidence_bundle_sha256": bundle["evidence_bundle_sha256"]},
        )
        request_path = preview_dir / "responses_request.json"
        _write_json(request_path, request)
        request_paths.append(request_path)
    return RequestReconstructionResult(tuple(request_paths), len(request_paths))


def run_interpretation(
    *,
    stage3_path: Path,
    config: InterpretationConfig,
    library: HypothesisLibrary,
    candidate_ranks: Sequence[int],
    episode_slug: str,
    system_prompt_path: Path,
    developer_prompt_path: Path,
    interim_root: Path,
    output_root: Path,
    force_regenerate: bool = False,
    provider_factory: Callable[[Any], InterpretationProvider] = OpenAIResponsesProvider,
) -> InterpretationRunResult:
    ranks = tuple(sorted(set(int(value) for value in candidate_ranks)))
    if not ranks:
        raise ValueError("at least one candidate rank is required")
    stage3 = json.loads(Path(stage3_path).read_text(encoding="utf-8"))
    candidates_by_rank = {int(value["rank"]): value for value in stage3["candidates"]}
    missing = sorted(set(ranks) - set(candidates_by_rank))
    if missing:
        raise ValueError(f"candidate ranks absent from Stage 3 output: {missing}")

    system_prompt = load_prompt(system_prompt_path)
    developer_prompt = load_prompt(developer_prompt_path)
    instructions = build_instructions(system_prompt, developer_prompt)
    schema = response_json_schema()
    schema_sha256 = _hash_bytes(canonical_json(schema).encode("utf-8"))
    identity = {
        "stage3_sha256": _hash_file(stage3_path),
        "configuration_sha256": config.fingerprint,
        "hypothesis_library_sha256": library.fingerprint,
        "system_prompt_sha256": _hash_file(system_prompt_path),
        "developer_prompt_sha256": _hash_file(developer_prompt_path),
        "response_schema_sha256": schema_sha256,
        "provider": config.provider.name,
        "model": config.provider.model,
        "reasoning_effort": config.provider.reasoning_effort,
        "store": config.provider.store,
        "max_output_tokens": config.provider.max_output_tokens,
    }
    episode_metadata = stage3["metadata"]
    output_dir = Path(output_root) / episode_slug / "turning_points" / "interpretation"
    output_json = output_dir / "interpretation.json"
    output_markdown = output_dir / "interpretation.md"
    result: dict[str, Any] = {
        "metadata": {
            "stage": "Stage 4 constrained LLM interpretation",
            "schema_version": config.schema_version,
            "prompt_version": config.prompt_version,
            "episode_slug": episode_slug,
            "episode_goal": episode_metadata["episode_goal"],
            "episode_goal_id": episode_metadata["episode_goal_id"],
            "candidate_ranks": list(ranks),
            "ranking_source": "frozen Stage 2 output",
            "ranking_is_immutable": True,
            "importance_score_added": False,
            "provider": config.provider.name,
            "requested_model": config.provider.model,
            "reasoning_effort": config.provider.reasoning_effort,
            "store": config.provider.store,
            "tools_enabled": False,
            "hypothesis_library_version": library.library_version,
            "hypothesis_library_status": library.library_status,
            "input_identity": identity,
        },
        "candidates": [],
    }
    provider: InterpretationProvider | None = None
    cache_reused_count = 0
    validated_count = 0

    for rank in ranks:
        candidate = candidates_by_rank[rank]
        bundle = build_evidence_bundle(
            candidate,
            episode_metadata=episode_metadata,
            library=library,
            config=config.evidence,
        )
        candidate_identity = {**identity, "evidence_bundle_sha256": bundle["evidence_bundle_sha256"], "candidate_rank": rank}
        # Keep Windows audit paths below legacy path-length limits; the full
        # identity is stored and checked inside the cache directory.
        cache_key = _hash_bytes(canonical_json(candidate_identity).encode("utf-8"))[:24]
        candidate_cache_dir = Path(interim_root) / episode_slug / "interpretation" / cache_key / f"candidate_{rank}"
        candidate_cache_dir.mkdir(parents=True, exist_ok=True)
        _write_json(candidate_cache_dir / "input_evidence_bundle.json", bundle)
        _write_json(candidate_cache_dir / "request_identity.json", candidate_identity)
        first_validated_path = candidate_cache_dir / "validated_interpretation.json"

        if first_validated_path.is_file() and config.cache.reuse_validated_by_default and not force_regenerate:
            cached = json.loads(first_validated_path.read_text(encoding="utf-8"))
            if cached.get("cache_identity") != candidate_identity:
                raise ValueError(f"cache identity mismatch for Candidate {rank}")
            cached["cache_reused"] = True
            result["candidates"].append(cached)
            cache_reused_count += 1
            validated_count += int(cached.get("interpretation_status") == "validated")
            continue

        generation_dir = _next_generation_dir(candidate_cache_dir)
        _write_json(
            generation_dir / "request_metadata.json",
            {
                "cache_identity": candidate_identity,
                "force_regenerate": force_regenerate,
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "one_request_per_candidate": True,
                "tools_enabled": False,
                "store": config.provider.store,
            },
        )
        if provider is None:
            provider = provider_factory(config.provider)

        validation_errors: tuple[str, ...] = ()
        previous_invalid_output: str | None = None
        candidate_result: dict[str, Any] | None = None
        for validation_attempt in range(1, config.provider.max_validation_attempts + 1):
            attempt_dir = generation_dir / f"attempt_{validation_attempt:03d}"
            attempt_dir.mkdir(parents=True, exist_ok=False)
            user_input = build_user_input(
                bundle,
                validation_errors=validation_errors,
                previous_invalid_output=previous_invalid_output,
            )
            _write_json(
                attempt_dir / "request.json",
                {
                    "instructions_sha256": _hash_bytes(instructions.encode("utf-8")),
                    "input_sha256": _hash_bytes(user_input.encode("utf-8")),
                    "schema_sha256": schema_sha256,
                    "repair_validation_errors": list(validation_errors),
                },
            )
            response = provider.generate(instructions=instructions, user_input=user_input, schema=schema)
            _write_json(attempt_dir / "raw_response.json", response.raw_response)
            _write_json(attempt_dir / "response_metadata.json", _model_response_metadata(response, validation_attempt))
            if response.refusal:
                _write_json(attempt_dir / "refusal.json", {"refusal": response.refusal})
                candidate_result = {
                    "behavioral_change_rank": rank,
                    "comparison_id": candidate["comparison_id"],
                    "turning_point_timestamp": candidate["turning_point_timestamp"],
                    "stage2_aggregate_score": candidate["aggregate_score"],
                    "stage3_reference": str(stage3_path),
                    "evidence_bundle_sha256": bundle["evidence_bundle_sha256"],
                    "deterministic_observations": bundle["deterministic_observations"],
                    "interpretation_status": "refused",
                    "failure_detail": response.refusal,
                    "model_response": _model_response_metadata(response, validation_attempt),
                    "cache_identity": candidate_identity,
                    "cache_reused": False,
                }
                break
            try:
                parsed = json.loads(response.output_text)
                _write_json(attempt_dir / "parsed_response.json", parsed)
            except json.JSONDecodeError as error:
                validation_errors = (f"invalid JSON: {error}",)
                previous_invalid_output = response.output_text
                _write_json(attempt_dir / "validation_errors.json", {"errors": list(validation_errors)})
                continue
            validation = validate_interpretation(
                parsed,
                evidence_bundle=bundle,
                library=library,
                rules=config.interpretation,
            )
            if not validation.valid:
                validation_errors = validation.errors
                previous_invalid_output = response.output_text
                _write_json(attempt_dir / "validation_errors.json", {"errors": list(validation_errors)})
                continue
            assert validation.validated_interpretation is not None
            candidate_result = {
                "behavioral_change_rank": rank,
                "comparison_id": candidate["comparison_id"],
                "turning_point_timestamp": candidate["turning_point_timestamp"],
                "stage2_aggregate_score": candidate["aggregate_score"],
                "stage3_reference": str(stage3_path),
                "evidence_bundle_sha256": bundle["evidence_bundle_sha256"],
                "deterministic_observations": bundle["deterministic_observations"],
                "interpretation_status": "validated",
                "interpretation": validation.validated_interpretation,
                "model_response": _model_response_metadata(response, validation_attempt),
                "cache_identity": candidate_identity,
                "cache_reused": False,
            }
            _write_json(attempt_dir / "validated_interpretation.json", candidate_result)
            if not first_validated_path.exists():
                _write_json(first_validated_path, candidate_result)
            else:
                _write_json(generation_dir / "regenerated_validated_interpretation.json", candidate_result)
            validated_count += 1
            break

        if candidate_result is None:
            candidate_result = {
                "behavioral_change_rank": rank,
                "comparison_id": candidate["comparison_id"],
                "turning_point_timestamp": candidate["turning_point_timestamp"],
                "stage2_aggregate_score": candidate["aggregate_score"],
                "stage3_reference": str(stage3_path),
                "evidence_bundle_sha256": bundle["evidence_bundle_sha256"],
                "deterministic_observations": bundle["deterministic_observations"],
                "interpretation_status": "failed_validation",
                "failure_detail": f"validation failed after {config.provider.max_validation_attempts} attempts",
                "validation_errors": list(validation_errors),
                "cache_identity": candidate_identity,
                "cache_reused": False,
            }
            _write_json(generation_dir / "failed_validation.json", candidate_result)
        result["candidates"].append(candidate_result)

    result["candidates"].sort(key=lambda value: value["behavioral_change_rank"])
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_json, result)
    output_markdown.write_text(render_markdown(result), encoding="utf-8", newline="\n")
    return InterpretationRunResult(output_json, output_markdown, len(ranks), validated_count, cache_reused_count)


__all__ = [
    "InterpretationRunResult",
    "RequestReconstructionResult",
    "ProviderAccessError",
    "reconstruct_interpretation_requests",
    "run_interpretation",
]
