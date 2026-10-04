"""Provider-neutral response shape and provider failures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class ProviderError(RuntimeError):
    """Base provider failure."""


class ProviderAccessError(ProviderError):
    """Missing credentials, denied model access, or other non-retryable access error."""


@dataclass(frozen=True)
class ProviderResponse:
    response_id: str | None
    model: str | None
    status: str | None
    output_text: str
    refusal: str | None
    usage: dict[str, Any]
    raw_response: dict[str, Any]


class InterpretationProvider(Protocol):
    def generate(self, *, instructions: str, user_input: str, schema: dict[str, Any]) -> ProviderResponse: ...
