"""OpenAI Responses API implementation for Stage 4."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .config import ProviderConfig
from .provider import ProviderAccessError, ProviderError, ProviderResponse


def _refusal_from_response(raw: dict[str, Any]) -> str | None:
    refusals: list[str] = []
    for item in raw.get("output", []):
        for content in item.get("content", []) if isinstance(item, dict) else []:
            if isinstance(content, dict) and content.get("type") == "refusal":
                refusals.append(str(content.get("refusal") or content.get("text") or "refused"))
    return "\n".join(refusals) or None


def load_project_environment(project_root: Path | None = None) -> Path:
    """Load repository-local secrets without replacing shell variables."""

    root = Path(project_root) if project_root is not None else Path(__file__).resolve().parents[3]
    dotenv_path = root / ".env"
    load_dotenv(dotenv_path=dotenv_path, override=False)
    return dotenv_path


def build_responses_request(
    config: ProviderConfig, *, instructions: str, user_input: str, schema: dict[str, Any]
) -> dict[str, Any]:
    """Build the exact secret-free Responses request used for generation and auditing."""

    return {
        "model": config.model,
        "instructions": instructions,
        "input": [{"role": "user", "content": [{"type": "input_text", "text": user_input}]}],
        "reasoning": {"effort": config.reasoning_effort},
        "tools": [],
        "store": config.store,
        "max_output_tokens": config.max_output_tokens,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "swarm_lens_stage4_interpretation",
                "strict": True,
                "schema": schema,
            }
        },
    }


class OpenAIResponsesProvider:
    def __init__(self, config: ProviderConfig) -> None:
        load_project_environment()
        if not os.environ.get("OPENAI_API_KEY"):
            raise ProviderAccessError("OPENAI_API_KEY is not configured; Stage 4 cannot call the approved model")
        try:
            from openai import OpenAI
        except ImportError as error:  # pragma: no cover - deployment guard
            raise ProviderAccessError("the openai Python package is not installed") from error
        self.config = config
        self.client = OpenAI(timeout=config.request_timeout_seconds, max_retries=0)

    def generate(self, *, instructions: str, user_input: str, schema: dict[str, Any]) -> ProviderResponse:
        last_error: Exception | None = None
        for transport_attempt in range(1, self.config.max_transport_attempts + 1):
            try:
                response = self.client.responses.create(
                    **build_responses_request(self.config, instructions=instructions, user_input=user_input, schema=schema)
                )
                raw = response.model_dump(mode="json")
                usage = raw.get("usage") or {}
                refusal = _refusal_from_response(raw)
                return ProviderResponse(
                    response_id=raw.get("id"),
                    model=raw.get("model"),
                    status=raw.get("status"),
                    output_text=response.output_text or "",
                    refusal=refusal,
                    usage=usage,
                    raw_response=raw,
                )
            except Exception as error:  # provider exception classes vary by SDK version
                last_error = error
                status_code = getattr(error, "status_code", None)
                error_name = type(error).__name__
                message = str(error)
                access_failure = status_code in {400, 401, 403, 404} or error_name in {
                    "AuthenticationError",
                    "PermissionDeniedError",
                    "NotFoundError",
                    "BadRequestError",
                }
                if access_failure:
                    raise ProviderAccessError(f"OpenAI access/configuration error ({error_name}, status={status_code}): {message}") from error
                if transport_attempt >= self.config.max_transport_attempts:
                    break
                time.sleep(self.config.transport_backoff_seconds * (2 ** (transport_attempt - 1)))
        assert last_error is not None
        raise ProviderError(
            f"OpenAI request failed after {self.config.max_transport_attempts} transport attempts: "
            f"{type(last_error).__name__}: {last_error}"
        ) from last_error
