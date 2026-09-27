"""Calls from the agent to the backend's /internal endpoints."""

import asyncio
import logging
import os
from typing import Any

import httpx

log = logging.getLogger("interviewer.api")


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=os.environ.get("API_BASE_URL", "http://localhost:8000"),
        headers={"X-Internal-Key": os.environ.get("INTERNAL_API_KEY", "dev-internal-key")},
        timeout=8.0,
    )


async def fetch_round_context(round_id: str) -> dict[str, Any]:
    async with _client() as c:
        r = await c.get(f"/internal/rounds/{round_id}/context")
        r.raise_for_status()
        return r.json()


async def complete_round(
    round_id: str,
    *,
    transcript: list[dict[str, Any]],
    final_code: str | None,
    final_whiteboard: str | None,
    hints_used: dict[str, int],
    question_notes: dict[str, str],
    end_reason: str,
) -> None:
    payload = {
        "transcript": transcript,
        "final_code": final_code,
        "final_whiteboard": final_whiteboard,
        "hints_used": hints_used,
        "question_notes": question_notes,
        "end_reason": end_reason,
    }
    # Runs during job shutdown, which has a ~10s budget: keep retries short.
    for attempt in range(3):
        try:
            async with _client() as c:
                r = await c.post(f"/internal/rounds/{round_id}/complete", json=payload)
                r.raise_for_status()
                return
        except httpx.HTTPError:
            log.exception("posting transcript failed (attempt %d)", attempt + 1)
            await asyncio.sleep(0.5 * (attempt + 1))
    log.error("giving up posting transcript for round %s", round_id)
