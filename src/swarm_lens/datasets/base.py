"""Small adapter contract; this is intentionally not a plugin framework."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

from swarm_lens.ingestion import BuildResult


@dataclass(frozen=True)
class ScopeDescriptor:
    scope_id: str
    title: str
    start: str
    end: str | None
    slug: str
    runnable: bool
    warnings: tuple[str, ...] = ()
    blocking_reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["warnings"] = list(self.warnings)
        return value


@dataclass(frozen=True)
class DatasetInspection:
    adapter_id: str
    dataset_fingerprint: str
    village_id: str
    source_counts: dict[str, int]
    scopes: tuple[ScopeDescriptor, ...]
    warnings: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "dataset_fingerprint": self.dataset_fingerprint,
            "village_id": self.village_id,
            "source_counts": self.source_counts,
            "scopes": [scope.as_dict() for scope in self.scopes],
            "warnings": list(self.warnings),
        }


class DatasetAdapter(Protocol):
    """Operations required by the first reusable-ingestion workflow."""

    adapter_id: str

    def inspect(self, raw_dir: Path) -> DatasetInspection: ...

    def materialize_scope(
        self,
        *,
        raw_dir: Path,
        scope_id: str,
        processed_root: Path,
        output_root: Path,
    ) -> BuildResult: ...

    def contextual_inputs(self, raw_dir: Path) -> dict[str, Path]: ...
