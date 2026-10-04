"""Export deterministic manual-adjudication packets for detected candidates."""

from __future__ import annotations

import argparse
from pathlib import Path

from swarm_lens.turning_points.context import export_candidate_context


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode", required=True, help="Ingested episode safe slug")
    parser.add_argument("--before-minutes", type=int, default=90)
    parser.add_argument("--after-minutes", type=int, default=90)
    parser.add_argument("--processed-root", type=Path, default=root / "data" / "processed" / "episodes")
    parser.add_argument("--output-root", type=Path, default=root / "outputs" / "episodes")
    parser.add_argument("--raw-dir", type=Path, default=root / "data" / "raw")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    turning_points = args.output_root / args.episode / "turning_points"
    packet = export_candidate_context(
        canonical_path=args.processed_root / args.episode / "events.parquet",
        candidates_path=turning_points / "top_candidates.parquet",
        raw_dir=args.raw_dir,
        changelog_path=args.raw_dir / "CHANGELOG.md",
        output_markdown=turning_points / "candidate_context.md",
        output_json=turning_points / "candidate_context.json",
        before_minutes=args.before_minutes,
        after_minutes=args.after_minutes,
    )
    print(f"candidates: {len(packet['candidates'])}")
    print(f"markdown: {turning_points / 'candidate_context.md'}")
    print(f"json: {turning_points / 'candidate_context.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
