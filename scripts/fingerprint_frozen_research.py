"""Print a presentation-independent fingerprint for frozen research outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from swarm_lens.research_fingerprint import research_content_fingerprint


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode", required=True)
    parser.add_argument(
        "--artifact-manifest",
        type=Path,
        default=root / "configs" / "frontend_episode_artifacts.toml",
    )
    parser.add_argument("--show-payload", action="store_true")
    args = parser.parse_args()
    fingerprint, payload = research_content_fingerprint(
        root, args.episode, args.artifact_manifest
    )
    print(f"episode: {args.episode}")
    print(f"research_content_fingerprint: {fingerprint}")
    if args.show_payload:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
