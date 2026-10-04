"""Deterministic fingerprints for frozen analytical content.

The frontend view model deliberately contains presentation wording and UI
metadata.  This module fingerprints the authoritative detector, evidence, and
interpretation artifacts instead, so presentation-only revisions do not look
like research regressions.
"""

from __future__ import annotations

import hashlib
import json
import tomllib
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping

import pyarrow.parquet as pq

from swarm_lens.interpretation.evidence_bundle import canonical_json


FINGERPRINT_VERSION = "1.0"


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        _json_safe(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _load_manifest_episode(manifest_path: Path, episode_slug: str) -> dict[str, Any]:
    with manifest_path.open("rb") as stream:
        manifest = tomllib.load(stream)
    if manifest.get("manifest_version") != "1.0":
        raise ValueError("unsupported frozen artifact-manifest version")
    try:
        episode = manifest["episodes"][episode_slug]
    except KeyError as error:
        raise ValueError(f"episode {episode_slug!r} is not pinned") from error
    ranks = episode.get("candidate_ranks")
    if ranks != list(range(1, len(ranks or []) + 1)):
        raise ValueError("pinned candidate ranks must be contiguous positive integers")
    keys = {int(rank): key for rank, key in episode.get("stage4_cache_keys", {}).items()}
    if sorted(keys) != ranks:
        raise ValueError("pinned interpretation caches do not cover every candidate")
    return {"ranks": ranks, "cache_keys": keys}


def _detector_candidates(path: Path) -> list[dict[str, Any]]:
    rows = sorted(pq.read_table(path).to_pylist(), key=lambda row: int(row["rank"]))
    result: list[dict[str, Any]] = []
    for row in rows:
        normalized = _json_safe(row)
        for component in ("communication", "intention", "participation", "action_type"):
            key = f"{component}_changes_json"
            normalized[f"{component}_changes"] = json.loads(normalized.pop(key))
        result.append(normalized)
    return result


def _brief_evidence_identities(brief: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "rank": int(candidate["rank"]),
            "comparison_id": candidate["comparison_id"],
            "evidence_items": [
                {
                    "display_key": item["display_key"],
                    "provenance": item["provenance"],
                }
                for item in candidate["evidence_items"]
            ],
        }
        for candidate in brief["candidates"]
    ]


def _reconstruction_identities(reconstruction: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "rank": int(candidate["rank"]),
            "comparison_id": candidate["comparison_id"],
            "turning_point_timestamp": candidate["turning_point_timestamp"],
            "ranked_preceding_evidence": [
                {
                    "rank": item["preceding_event_rank"],
                    "logical_item_id": item["logical_item_id"],
                    "evidence_label": item["evidence_label"],
                    "antecedent_support": item["antecedent_support"],
                    "provenance": item["provenance"],
                }
                for item in candidate["ranked_preceding_events"]
            ],
        }
        for candidate in reconstruction["candidates"]
    ]


def build_research_content_payload(
    root: Path,
    episode_slug: str,
    manifest_path: Path | None = None,
) -> dict[str, Any]:
    """Build the normalized upstream research identity for one frozen episode."""

    root = Path(root).resolve()
    manifest_path = (
        Path(manifest_path).resolve()
        if manifest_path is not None
        else root / "configs" / "frontend_episode_artifacts.toml"
    )
    pinned = _load_manifest_episode(manifest_path, episode_slug)
    output_dir = root / "outputs" / "episodes" / episode_slug / "turning_points"
    interim_dir = root / "data" / "interim" / "episodes" / episode_slug
    resolved = json.loads(
        (output_dir / "resolved_configuration.json").read_text(encoding="utf-8")
    )
    brief = json.loads((output_dir / "candidate_brief.json").read_text(encoding="utf-8"))
    reconstruction_path = output_dir / "evidence_reconstruction" / "evidence_reconstruction.json"
    reconstruction = json.loads(reconstruction_path.read_text(encoding="utf-8"))
    candidates = _detector_candidates(output_dir / "top_candidates.parquet")
    ranks = [int(candidate["rank"]) for candidate in candidates]
    if ranks != pinned["ranks"]:
        raise ValueError(f"detector ranks {ranks} do not match pinned ranks {pinned['ranks']}")
    if [int(candidate["rank"]) for candidate in brief["candidates"]] != ranks:
        raise ValueError("evidence-brief ordering does not match detector ordering")
    if [int(candidate["rank"]) for candidate in reconstruction["candidates"]] != ranks:
        raise ValueError("reconstruction ordering does not match detector ordering")

    reconstruction_file_sha256 = _file_hash(reconstruction_path)
    interpretations: list[dict[str, Any]] = []
    for rank in ranks:
        cache_key = pinned["cache_keys"][rank]
        cache_dir = interim_dir / "interpretation" / cache_key / f"candidate_{rank}"
        identity = json.loads((cache_dir / "request_identity.json").read_text(encoding="utf-8"))
        calculated_key = hashlib.sha256(canonical_json(identity).encode("utf-8")).hexdigest()[:24]
        if calculated_key != cache_key:
            raise ValueError(f"interpretation cache identity mismatch for rank {rank}")
        if identity.get("stage3_sha256") != reconstruction_file_sha256:
            raise ValueError(f"interpretation rank {rank} does not reference this reconstruction")
        validated = json.loads(
            (cache_dir / "validated_interpretation.json").read_text(encoding="utf-8")
        )
        if int(validated.get("behavioral_change_rank", 0)) != rank:
            raise ValueError(f"validated interpretation rank mismatch for rank {rank}")
        analytical_interpretation = {
            "behavioral_change_rank": validated["behavioral_change_rank"],
            "comparison_id": validated["comparison_id"],
            "turning_point_timestamp": validated["turning_point_timestamp"],
            "stage2_aggregate_score": validated["stage2_aggregate_score"],
            "stage3_reference": validated["stage3_reference"],
            "evidence_bundle_sha256": validated["evidence_bundle_sha256"],
            "interpretation_status": validated["interpretation_status"],
            "interpretation": validated["interpretation"],
        }
        interpretations.append(
            {
                "rank": rank,
                "cache_key": cache_key,
                "request_identity": identity,
                "validated_analytical_content_sha256": _canonical_hash(
                    analytical_interpretation
                ),
                "validated_analytical_content": analytical_interpretation,
            }
        )

    return {
        "fingerprint_version": FINGERPRINT_VERSION,
        "episode_slug": episode_slug,
        "behavioral_change_detection": {
            "canonical_input_sha256": resolved["canonical_input_sha256"],
            "configuration_sha256": resolved["configuration_sha256"],
            "recommended_window_minutes": resolved["recommended_window_minutes"],
            "candidates": candidates,
        },
        "evidence_brief": {
            "canonical_content_sha256": _canonical_hash(brief),
            "evidence_identities": _brief_evidence_identities(brief),
        },
        "evidence_reconstruction": {
            "file_sha256": reconstruction_file_sha256,
            "canonical_content_sha256": _canonical_hash(reconstruction),
            "configuration_sha256": reconstruction["metadata"]["configuration_sha256"],
            "candidate_identities": _reconstruction_identities(reconstruction),
        },
        "analyst_interpretation": {
            "candidates": interpretations,
        },
    }


def research_content_fingerprint(
    root: Path,
    episode_slug: str,
    manifest_path: Path | None = None,
) -> tuple[str, dict[str, Any]]:
    payload = build_research_content_payload(root, episode_slug, manifest_path)
    return _canonical_hash(payload), payload
