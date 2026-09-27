"""Thin wrapper over the Anthropic SDK for the structured (JSON) calls the API makes.

Every call here is a one-off, non-latency-sensitive job (resume parsing, planning,
evaluation), so we use the smart model with adaptive thinking and validate the reply
against a Pydantic schema via structured outputs.
"""

import logging
from typing import Literal, TypeVar

import anthropic
from pydantic import BaseModel

from app.config import get_settings

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)
Effort = Literal["low", "medium", "high"]


class LLMError(RuntimeError):
    """The model could not produce a usable answer (refusal, truncation, API failure)."""


_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        settings = get_settings()
        # Falls back to the SDK's own credential resolution when the key is unset.
        kwargs = {"api_key": settings.anthropic_api_key} if settings.anthropic_api_key else {}
        _client = anthropic.Anthropic(max_retries=3, timeout=300.0, **kwargs)
    return _client


def structured(
    *,
    system: str,
    user: str,
    schema: type[T],
    effort: Effort = "medium",
    max_tokens: int = 16000,
    model: str | None = None,
) -> T:
    settings = get_settings()
    try:
        response = _get_client().messages.parse(
            model=model or settings.llm_model_smart,
            max_tokens=max_tokens,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
            thinking={"type": "adaptive"},
            output_config={"effort": effort},
            output_format=schema,
        )
    except anthropic.APIStatusError as e:
        log.exception("Anthropic API error (status=%s)", e.status_code)
        raise LLMError(f"LLM request failed with status {e.status_code}") from e
    except anthropic.APIConnectionError as e:
        log.exception("Anthropic connection error")
        raise LLMError("Could not reach the LLM provider") from e

    if response.stop_reason == "refusal":
        raise LLMError("The model declined this request")
    if response.stop_reason == "max_tokens":
        raise LLMError("The model ran out of output tokens")
    if response.parsed_output is None:
        raise LLMError("The model returned output that did not match the schema")

    log.info(
        "llm call schema=%s in=%s out=%s cache_read=%s",
        schema.__name__,
        response.usage.input_tokens,
        response.usage.output_tokens,
        response.usage.cache_read_input_tokens,
    )
    return response.parsed_output
