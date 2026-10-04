"""Worker subprocess entry point for one isolated SwarmLens run."""

from __future__ import annotations

import argparse
from pathlib import Path

from swarm_lens.execution import JobRegistry, PipelineRunner, WorkspaceLayout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--workspace-root", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--mode", choices=("deterministic", "interpret"), required=True)
    args = parser.parse_args()
    runner = PipelineRunner(
        registry=JobRegistry(args.registry),
        layout=WorkspaceLayout.under(args.repository_root, args.workspace_root),
    )
    if args.mode == "deterministic":
        runner.run_deterministic(args.run_id)
    else:
        runner.run_interpretation_and_package(args.run_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
