"""Run constrained Stage 4 interpretation for selected frozen candidates."""

from __future__ import annotations

import argparse
from pathlib import Path

from swarm_lens.interpretation.config import load_config
from swarm_lens.interpretation.hypotheses import load_hypothesis_library
from swarm_lens.interpretation.pipeline import reconstruct_interpretation_requests, run_interpretation


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode", required=True, help="Episode safe slug")
    parser.add_argument("--candidate-rank", type=int, action="append", required=True, help="Frozen Stage 2 rank; repeat as needed")
    parser.add_argument("--config", type=Path, default=root / "configs" / "interpretation.toml")
    parser.add_argument("--hypothesis-library", type=Path, default=root / "configs" / "social_process_hypotheses.toml")
    parser.add_argument("--system-prompt", type=Path, default=root / "prompts" / "stage4_system_v1.txt")
    parser.add_argument("--developer-prompt", type=Path, default=root / "prompts" / "stage4_developer_v1.txt")
    parser.add_argument("--interim-root", type=Path, default=root / "data" / "interim" / "episodes")
    parser.add_argument("--output-root", type=Path, default=root / "outputs" / "episodes")
    parser.add_argument("--force-regenerate", action="store_true", help="Make a new API request even when a validated cache entry exists")
    parser.add_argument("--reconstruct-only", action="store_true", help="Write exact request previews without constructing a provider or calling the API")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    library = load_hypothesis_library(args.hypothesis_library, confidence_levels=config.interpretation.confidence_levels)
    stage3_path = args.output_root / args.episode / "turning_points" / "evidence_reconstruction" / "evidence_reconstruction.json"
    if args.reconstruct_only:
        result = reconstruct_interpretation_requests(
            stage3_path=stage3_path,
            config=config,
            library=library,
            candidate_ranks=args.candidate_rank,
            episode_slug=args.episode,
            system_prompt_path=args.system_prompt,
            developer_prompt_path=args.developer_prompt,
            interim_root=args.interim_root,
        )
        print(f"candidates: {result.candidate_count}")
        print("model_calls: 0")
        for path in result.request_paths:
            print(f"request: {path}")
        return 0
    result = run_interpretation(
        stage3_path=stage3_path,
        config=config,
        library=library,
        candidate_ranks=args.candidate_rank,
        episode_slug=args.episode,
        system_prompt_path=args.system_prompt,
        developer_prompt_path=args.developer_prompt,
        interim_root=args.interim_root,
        output_root=args.output_root,
        force_regenerate=args.force_regenerate,
    )
    print(f"candidates: {result.candidate_count}")
    print(f"validated: {result.validated_count}")
    print(f"cache_reused: {result.cache_reused_count}")
    print(f"json: {result.output_json}")
    print(f"markdown: {result.output_markdown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
