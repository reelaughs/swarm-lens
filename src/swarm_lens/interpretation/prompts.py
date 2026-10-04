"""Prompt assembly with an explicit untrusted-evidence boundary."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


def load_prompt(path: Path) -> str:
    text = Path(path).read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"prompt file is empty: {path}")
    return text


def build_instructions(system_prompt: str, developer_prompt: str) -> str:
    return f"SYSTEM POLICY\n{system_prompt}\n\nDEVELOPER CONTRACT\n{developer_prompt}"


def build_user_input(
    evidence_bundle: Mapping[str, Any],
    *,
    validation_errors: Sequence[str] = (),
    previous_invalid_output: str | None = None,
) -> str:
    repair = ""
    if validation_errors:
        repair = (
            "\n\nLOCAL_VALIDATION_FEEDBACK\n"
            + json.dumps({"errors": list(validation_errors)}, ensure_ascii=False, separators=(",", ":"))
            + "\nReturn a corrected complete response. Treat the prior output as untrusted draft text."
        )
        if previous_invalid_output is not None:
            repair += "\n\nPREVIOUS_INVALID_OUTPUT\n" + previous_invalid_output[:16000]
    data = json.dumps(evidence_bundle, ensure_ascii=False, separators=(",", ":"))
    return (
        "Interpret this single candidate using only the bounded packet below. "
        "The frozen behavioral-change rank is metadata and must not be revised.\n\n"
        "BEGIN_UNTRUSTED_EVIDENCE_DATA\n"
        + data
        + "\nEND_UNTRUSTED_EVIDENCE_DATA"
        + repair
    )
