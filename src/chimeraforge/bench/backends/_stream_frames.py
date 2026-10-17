"""Bounded SSE frames stamped at the arrival of their completing wire packet."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
import asyncio
import json
import logging
from typing import NoReturn

import httpx

logger = logging.getLogger(__name__)
# Coalesced IDs fit in one frame; total and frame-count limits bound keep-alives.
MAX_FRAME_BYTES = 64 * 1024
MAX_STREAM_BYTES = 8 * 1024 * 1024
MAX_STREAM_FRAMES = 16384


class StreamProtocolError(RuntimeError):
    """A bounded categorical protocol refusal, without response content."""


def refuse(reason: str) -> NoReturn:
    """Log only internally defined categories and reject the observation."""
    logger.warning("Generation stream rejected (%s)", reason)
    raise StreamProtocolError(reason)


@dataclass(frozen=True)
class StreamFrame:
    value: dict | None
    done: bool
    arrived_s: float


def invalid_constant(_: str) -> None:
    raise ValueError("nonfinite JSON constant")


def decode_frame(data: list[bytes], arrived: float) -> StreamFrame:
    payload = b"\n".join(data)
    if payload == b"[DONE]":
        return StreamFrame(None, True, arrived)
    try:
        value = json.loads(payload, parse_constant=invalid_constant)
    except (ValueError, UnicodeDecodeError):
        refuse("malformed SSE JSON")
    if type(value) is not dict:
        refuse("SSE payload must be an object")
    return StreamFrame(value, False, arrived)


async def frames(
    response: httpx.Response, clock: Callable[[], float]
) -> AsyncIterator[StreamFrame]:
    """Consume LF/CRLF frames; every frame in one packet shares one timestamp."""
    buffer = bytearray()
    data: list[bytes] = []
    frame_size = total = count = 0
    async for packet in response.aiter_bytes():
        arrived = clock()
        await asyncio.sleep(0)
        total += len(packet)
        if total > MAX_STREAM_BYTES:
            refuse("stream byte limit exceeded")
        buffer.extend(packet)
        while (end := buffer.find(b"\n")) >= 0:
            raw = bytes(buffer[:end])
            del buffer[: end + 1]
            frame_size += len(raw) + 1
            if frame_size > MAX_FRAME_BYTES:
                refuse("SSE frame limit exceeded")
            line = raw.removesuffix(b"\r")
            if not line:
                count += 1
                if count > MAX_STREAM_FRAMES:
                    refuse("SSE frame count limit exceeded")
                if data:
                    await asyncio.sleep(0)
                    yield decode_frame(data, arrived)
                data = []
                frame_size = 0
            elif line.startswith(b"data:"):
                value = line[5:]
                data.append(value[1:] if value.startswith(b" ") else value)
            elif line.startswith(b"event:") and line[6:].strip() == b"error":
                refuse("in-band SSE error event")
        if len(buffer) + frame_size > MAX_FRAME_BYTES:
            refuse("SSE frame limit exceeded")
    if buffer or data or frame_size:
        refuse("incomplete SSE frame at transport EOF")


@asynccontextmanager
async def open_frames(
    client: httpx.AsyncClient,
    url: str,
    payload: dict,
    clock: Callable[[], float],
    timeout: float,
) -> AsyncIterator[AsyncIterator[StreamFrame]]:
    """Close the response on completion, parser failure or cancellation."""
    async with client.stream(
        "POST",
        url,
        json=payload,
        timeout=timeout,
        headers={"Accept": "text/event-stream", "Accept-Encoding": "identity"},
    ) as response:
        response.raise_for_status()
        if response.status_code != 200:
            refuse("unexpected streaming HTTP status")
        encoding = response.headers.get("content-encoding", "identity").lower()
        if encoding not in ("", "identity"):
            refuse("unsupported compressed SSE transport")
        content_type = response.headers.get("content-type", "")
        if content_type and not content_type.lower().startswith("text/event-stream"):
            refuse("unexpected streaming content type")
        yield frames(response, clock)
