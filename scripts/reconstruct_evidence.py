"""Reconstruct process-neutral evidence around frozen Stage 2 candidates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from swarm_lens.evidence_reconstruction import load_config, run_reconstruction


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode", required=True, help="Ingested episode safe slug")
    parser.add_argument("--candidate-rank", type=int, action="append", required=True, help="Frozen Stage 2 rank; repeat for multiple candidates")
    parser.add_argument("--config", type=Path, default=root / "configs" / "evidence_reconstruction.toml")
    parser.add_argument("--processed-root", type=Path, default=root / "data" / "processed" / "episodes")
    parser.add_argument("--interim-root", type=Path, default=root / "data" / "interim" / "episodes")
    parser.add_argument("--output-root", type=Path, default=root / "outputs" / "episodes")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    turning_points = args.output_root / args.episode / "turning_points"
    resolved_path = turning_points / "resolved_configuration.json"
    resolved = json.loads(resolved_path.read_text(encoding="utf-8"))
    stage2_cache_name = f"{resolved['configuration_sha256'][:12]}-{resolved['canonical_input_sha256'][:12]}"
    result = run_reconstruction(
        canonical_path=args.processed_root / args.episode / "events.parquet",
        candidates_path=turning_points / "top_candidates.parquet",
        candidate_context_path=turning_points / "candidate_context.json",
        candidate_brief_path=turning_points / "candidate_brief.json",
        inactive_gaps_path=turning_points / "inactive_gaps.csv",
        stage2_resolved_config_path=resolved_path,
        stage2_cache_dir=args.interim_root / args.episode / "turning_points" / stage2_cache_name,
        config=load_config(args.config),
        candidate_ranks=args.candidate_rank,
        episode_slug=args.episode,
        interim_root=args.interim_root,
        output_root=args.output_root,
    )
    print(f"candidates: {result.candidate_count}")
    print(f"cache_hit: {result.cache_hit}")
    print(f"cache_dir: {result.cache_dir}")
    print(f"json: {result.output_json}")
    print(f"markdown: {result.output_markdown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
