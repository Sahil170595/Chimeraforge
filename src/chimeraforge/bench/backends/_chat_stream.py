"""Native text-chat SSE; optional usage never becomes a count of wire chunks."""

from __future__ import annotations

from collections.abc import Callable
import httpx

from chimeraforge.bench.backends.base import GenerationObservation
from chimeraforge.bench.backends._native_stream import NativeTiming, count, SUCCESSFUL_OPENAI_FINISH
from chimeraforge.bench.backends._stream_frames import open_frames, refuse

NON_TEXT_FIELDS = (
    "tool_calls",
    "function_call",
    "reasoning",
    "reasoning_content",
    "thinking",
    "audio",
    "refusal",
    "images",
)


def plain_content(delta: object) -> str:
    if type(delta) is not dict:
        refuse("chat delta must be an object")
    if delta.get("role") not in (None, "assistant"):
        refuse("chat output role is unsupported")
    if any(delta.get(name) not in (None, "", [], {}) for name in NON_TEXT_FIELDS):
        refuse("non-text chat output is unsupported")
    text = delta.get("content")
    if text is not None and type(text) is not str:
        refuse("chat content is not plain text")
    return text or ""


def chat_count(value: object, name: str) -> int:
    from chimeraforge.bench.gate_inputs import MAX_TOKEN_COUNT

    result = count(value, name)
    if result > MAX_TOKEN_COUNT:
        refuse("chat native count exceeds receiving domain")
    return result


def optional_usage(value: dict) -> tuple[int | None, int | None, int | None]:
    output_details = value.get("completion_tokens_details")
    if output_details is not None and type(output_details) is not dict:
        refuse("invalid chat completion details")
    for generated in (
        value.get("reasoning_tokens"),
        (output_details or {}).get("reasoning_tokens"),
        (output_details or {}).get("audio_tokens"),
    ):
        if generated is not None and count(generated, "generated non-text count") > 0:
            refuse("generated non-text chat usage is unsupported")
    output = (
        chat_count(value["completion_tokens"], "chat output count")
        if value.get("completion_tokens") is not None
        else None
    )
    prompt = (
        chat_count(value["prompt_tokens"], "chat prompt count")
        if value.get("prompt_tokens") is not None
        else None
    )
    if value.get("total_tokens") is not None:
        total = count(value["total_tokens"], "chat total count")
        if (output is not None and total < output) or (prompt is not None and total < prompt):
            refuse("inconsistent chat total count")
        if output is not None and prompt is not None and total != output + prompt:
            refuse("inconsistent chat total count")
    details = value.get("prompt_tokens_details")
    if details is not None and type(details) is not dict:
        refuse("invalid chat prompt details")
    reported = [
        v
        for v in (value.get("cached_tokens"), (details or {}).get("cached_tokens"))
        if v is not None
    ]
    cache = chat_count(reported[0], "chat cached count") if reported else None
    if cache is not None and (
        (prompt is not None and cache > prompt)
        or any(chat_count(v, "chat cached count") != cache for v in reported)
    ):
        refuse("inconsistent chat cached count")
    return output, prompt, cache


async def observe_chat(
    client: httpx.AsyncClient,
    url: str,
    payload: dict,
    clock: Callable[[], float],
    timeout: float,
    callback: Callable[[], None],
) -> GenerationObservation:
    timing = NativeTiming(clock(), count(payload.get("max_tokens"), "chat output cap"))
    finish = done = False
    usage: tuple[int | None, int | None, int | None] | None = None
    body = {**payload, "stream": True, "n": 1, "stream_options": {"include_usage": True}}
    async with open_frames(client, url, body, clock, timeout) as incoming:
        async for frame in incoming:
            if done:
                refuse("chat data after terminal DONE")
            if frame.done:
                if not finish:
                    refuse("chat DONE without successful finish")
                done = True
                continue
            value = frame.value
            assert value is not None
            if "error" in value or "error_type" in value:
                refuse("in-band chat error")
            choices = value.get("choices")
            if type(choices) is not list:
                refuse("invalid chat choices")
            reported = value.get("usage")
            if reported is not None:
                if choices or not finish or usage is not None or type(reported) is not dict:
                    refuse("unexpected chat usage")
                usage = optional_usage(reported)
                continue
            if len(choices) != 1 or finish or usage is not None:
                refuse("unexpected chat choice population")
            item = choices[0]
            if type(item) is not dict or type(item.get("index")) is not int or item["index"] != 0:
                refuse("unexpected chat choice index")
            timing.visible(plain_content(item.get("delta")), frame.arrived_s, callback)
            reason = item.get("finish_reason")
            if reason is not None:
                if type(reason) is not str or reason not in SUCCESSFUL_OPENAI_FINISH:
                    refuse("unsupported chat finish reason")
                finish = True
    if not done:
        refuse("incomplete chat transport")
    output, prompt, cache = usage if usage is not None else (None, None, None)
    return timing.observation(output, prompt, cache, clock())
