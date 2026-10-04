"""Create compact deterministic candidate briefs from frozen detector outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from swarm_lens.turning_points.brief import export_candidate_brief


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode", required=True, help="Ingested episode safe slug")
    parser.add_argument("--interim-root", type=Path, default=root / "data" / "interim" / "episodes")
    parser.add_argument("--output-root", type=Path, default=root / "outputs" / "episodes")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    turning_points = args.output_root / args.episode / "turning_points"
    resolved = json.loads((turning_points / "resolved_configuration.json").read_text(encoding="utf-8"))
    cache_name = f"{resolved['configuration_sha256'][:12]}-{resolved['canonical_input_sha256'][:12]}"
    topic_features = args.interim_root / args.episode / "turning_points" / cache_name / "topic_features.parquet"
    brief = export_candidate_brief(
        context_json=turning_points / "candidate_context.json",
        candidates_path=turning_points / "top_candidates.parquet",
        topic_features_path=topic_features,
        output_markdown=turning_points / "candidate_brief.md",
        output_json=turning_points / "candidate_brief.json",
    )
    print(f"candidates: {len(brief['candidates'])}")
    print("displayed_items:", ", ".join(f"{item['rank']}={item['displayed_evidence_item_count']}" for item in brief["candidates"]))
    print(f"markdown: {turning_points / 'candidate_brief.md'}")
    print(f"json: {turning_points / 'candidate_brief.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
