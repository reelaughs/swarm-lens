"""Command-line entry point for the generic SwarmLens episode builder."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from swarm_lens.ingestion import IngestionError, build_episode


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Build canonical events for one village-goal episode.")
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--goal", help="Exact village goal text")
    selector.add_argument("--goal-id", help="Exact village goal UUID")
    parser.add_argument("--raw-dir", type=Path, default=repo_root / "data" / "raw")
    parser.add_argument("--processed-root", type=Path, default=repo_root / "data" / "processed" / "episodes")
    parser.add_argument("--output-root", type=Path, default=repo_root / "outputs" / "episodes")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = build_episode(
            raw_dir=args.raw_dir,
            processed_root=args.processed_root,
            output_root=args.output_root,
            goal=args.goal,
            goal_id=args.goal_id,
        )
    except IngestionError as exc:
        print(f"ingestion failed: {exc}", file=sys.stderr)
        return 1
    print(f"episode: {result.episode.goal} ({result.episode.id})")
    print(f"rows: {result.row_count}")
    print(f"parquet: {result.parquet_path}")
    print(f"report: {result.report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
