"""Count tokens for reconstructed Stage 4 requests without generating a response."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from openai import OpenAI

from swarm_lens.interpretation.openai_provider import load_project_environment


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", type=Path, nargs="+", help="Secret-free Responses request preview")
    parser.add_argument("--breakdown", action="store_true", help="Also count isolated compact bundle sections")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_project_environment()
    client = OpenAI()
    allowed = {"model", "instructions", "input", "reasoning", "tools", "text"}
    for path in args.request:
        request = json.loads(path.read_text(encoding="utf-8"))
        response = client.responses.input_tokens.count(**{key: value for key, value in request.items() if key in allowed})
        print(f"{path}: {response.input_tokens}")
        if args.breakdown:
            bundle_path = path.with_name("input_evidence_bundle.json")
            bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
            base = client.responses.input_tokens.count(model=request["model"], input=" ").input_tokens

            def isolated(value) -> int:
                text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
                return client.responses.input_tokens.count(model=request["model"], input=text).input_tokens - base

            observations = bundle["deterministic_observations"]
            sections = {
                "candidate_reference": bundle["candidate_reference"],
                "interpretation_constraints": bundle["interpretation_constraints"],
                "raw_record_evidence": observations["raw_record_evidence"],
                "derived_measurements": observations["derived_measurements"],
                "contextual_observations": observations["contextual_observations"],
                "evidence_id_to_provenance": bundle["evidence_id_to_provenance"],
                "hypothesis_library": bundle["hypothesis_library"],
                "bundle_metadata_and_hash": {
                    "bundle_version": bundle["bundle_version"],
                    "evidence_bundle_sha256": bundle["evidence_bundle_sha256"],
                },
            }
            for name, value in sections.items():
                item_count = len(value) if isinstance(value, (list, dict)) else 1
                print(f"  {name}: approximately {isolated(value)} tokens; items={item_count}")
            instruction_tokens = (
                client.responses.input_tokens.count(
                    model=request["model"], instructions=request["instructions"], input=" "
                ).input_tokens
                - base
            )
            schema_tokens = (
                client.responses.input_tokens.count(
                    model=request["model"], input=" ", text=request["text"]
                ).input_tokens
                - base
            )
            print(f"  instructions: approximately {instruction_tokens} tokens; items=2 prompt sections")
            print(f"  response_schema: approximately {schema_tokens} tokens; items=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
