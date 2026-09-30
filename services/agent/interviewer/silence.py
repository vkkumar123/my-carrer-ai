"""Lets the interviewer choose silence: an LLM reply of exactly "<wait>" is never spoken."""

from collections.abc import AsyncIterable, AsyncIterator
from typing import Any

WAIT = "<wait>"


def _text(chunk: Any) -> str | None:
    if isinstance(chunk, str):
        return chunk
    delta = getattr(chunk, "delta", None)
    return getattr(delta, "content", None) if delta is not None else None


def _has_tool_call(chunk: Any) -> bool:
    delta = getattr(chunk, "delta", None)
    return bool(delta is not None and getattr(delta, "tool_calls", None))


def _strip_marker(chunk: Any) -> Any:
    """Remove a stray <wait> inside otherwise spoken text."""
    if isinstance(chunk, str):
        return chunk.replace(WAIT, "")
    delta = getattr(chunk, "delta", None)
    if delta is not None and delta.content and WAIT in delta.content:
        delta.content = delta.content.replace(WAIT, "")
    return chunk


async def drop_wait(stream: AsyncIterable[Any]) -> AsyncIterator[Any]:
    """Pass the LLM stream through, unless the reply is the silent marker.

    The first text is buffered until it is clearly not "<wait>" (the marker can arrive split
    across chunks). Tool calls and non-text chunks (usage, metadata) always pass through.
    """
    buffered: list[Any] = []
    text = ""
    state = "undecided"  # -> "speak" | "silent"
    async for chunk in stream:
        if state == "speak":
            yield _strip_marker(chunk)
            continue
        content = _text(chunk)
        if state == "silent":
            if content is None or _has_tool_call(chunk):
                yield chunk
            continue
        if _has_tool_call(chunk):
            state = "speak"
        elif content is not None:
            text += content
            probe = text.lstrip()
            if probe.startswith(WAIT):
                state = "silent"
                for b in buffered:  # keep usage/metadata chunks that arrived earlier
                    if _text(b) is None:
                        yield b
                buffered = []
                continue
            if probe and not WAIT.startswith(probe):
                state = "speak"
        buffered.append(chunk)
        if state == "speak":
            for b in buffered:
                yield _strip_marker(b)
            buffered = []
    if state == "undecided":
        probe = text.strip()
        if probe and not WAIT.startswith(probe):  # e.g. "<" alone would be odd; speak it
            for b in buffered:
                yield b
        else:
            for b in buffered:
                if _text(b) is None:
                    yield b
