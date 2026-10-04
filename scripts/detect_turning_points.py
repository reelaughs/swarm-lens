"""Run Stage 2 population-level turning-point detection for one ingested episode."""

from __future__ import annotations

import argparse
from pathlib import Path

from swarm_lens.turning_points import load_config, run_detection


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode", required=True, help="Ingested episode safe slug")
    parser.add_argument("--config", type=Path, default=root / "configs" / "turning_points.toml")
    parser.add_argument("--processed-root", type=Path, default=root / "data" / "processed" / "episodes")
    parser.add_argument("--interim-root", type=Path, default=root / "data" / "interim" / "episodes")
    parser.add_argument("--output-root", type=Path, default=root / "outputs" / "episodes")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    result = run_detection(
        canonical_path=args.processed_root / args.episode / "events.parquet",
        episode_slug=args.episode,
        config=config,
        interim_root=args.interim_root,
        output_root=args.output_root,
    )
    print(f"recommended_window_minutes: {result.recommended_window_minutes}")
    print(f"candidate_count: {result.candidate_count}")
    print(f"output_dir: {result.output_dir}")
    print(f"cache_dir: {result.cache_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
