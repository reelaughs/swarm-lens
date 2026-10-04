"""Extensible, provisional social-process hypothesis library."""

from __future__ import annotations

import hashlib
import json
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Signature:
    id: str
    description: str


@dataclass(frozen=True)
class CounterSignature:
    id: str
    description: str
    confidence_cap: str


@dataclass(frozen=True)
class Hypothesis:
    id: str
    name: str
    description: str
    required_signature_ids_for_high_confidence: tuple[str, ...]
    context_only_confidence_cap: str
    signatures: tuple[Signature, ...]
    counter_signatures: tuple[CounterSignature, ...]
    cautions: tuple[str, ...]

    @property
    def signature_ids(self) -> set[str]:
        return {value.id for value in self.signatures}

    @property
    def counter_signature_ids(self) -> set[str]:
        return {value.id for value in self.counter_signatures}


@dataclass(frozen=True)
class HypothesisLibrary:
    library_version: str
    library_status: str
    hypotheses: tuple[Hypothesis, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def fingerprint(self) -> str:
        payload = json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(payload).hexdigest()

    @property
    def by_id(self) -> dict[str, Hypothesis]:
        return {value.id: value for value in self.hypotheses}


def load_hypothesis_library(path: Path, *, confidence_levels: tuple[str, ...] = ("low", "moderate", "high")) -> HypothesisLibrary:
    with Path(path).open("rb") as stream:
        raw = tomllib.load(stream)
    hypotheses = []
    for item in raw.get("hypotheses", []):
        signatures = tuple(Signature(**value) for value in item.get("signatures", []))
        counters = tuple(CounterSignature(**value) for value in item.get("counter_signatures", []))
        cautions = tuple(value["text"] for value in item.get("cautions", []))
        hypothesis = Hypothesis(
            id=item["id"],
            name=item["name"],
            description=item["description"],
            required_signature_ids_for_high_confidence=tuple(item.get("required_signature_ids_for_high_confidence", [])),
            context_only_confidence_cap=item.get("context_only_confidence_cap", "low"),
            signatures=signatures,
            counter_signatures=counters,
            cautions=cautions,
        )
        if not hypothesis.signatures:
            raise ValueError(f"hypothesis {hypothesis.id!r} has no signatures")
        signature_ids = [value.id for value in signatures]
        counter_ids = [value.id for value in counters]
        if len(signature_ids) != len(set(signature_ids)) or len(counter_ids) != len(set(counter_ids)):
            raise ValueError(f"duplicate signature ID in hypothesis {hypothesis.id!r}")
        unknown_required = set(hypothesis.required_signature_ids_for_high_confidence) - hypothesis.signature_ids
        if unknown_required:
            raise ValueError(f"hypothesis {hypothesis.id!r} has unknown high-confidence signatures: {sorted(unknown_required)}")
        caps = [hypothesis.context_only_confidence_cap, *(value.confidence_cap for value in counters)]
        if any(value not in confidence_levels for value in caps):
            raise ValueError(f"hypothesis {hypothesis.id!r} has an invalid confidence cap")
        hypotheses.append(hypothesis)
    ids = [value.id for value in hypotheses]
    if len(ids) != len(set(ids)):
        raise ValueError("hypothesis IDs must be unique")
    if not hypotheses:
        raise ValueError("hypothesis library must contain at least one hypothesis")
    return HypothesisLibrary(str(raw["library_version"]), str(raw["library_status"]), tuple(hypotheses))
