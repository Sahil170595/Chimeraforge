"""Native counts and client-arrival timing, with explicit completion proof."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import httpx

from chimeraforge.bench.backends.base import GenerationObservation
from chimeraforge.bench.backends._stream_frames import open_frames, refuse
from chimeraforge.bench.metrics import RunMetrics

CLIENT_NATIVE_TPOT_BASIS = "client-first-to-last-native-output/(server-output-count-1)"
SUCCESSFUL_OPENAI_FINISH = frozenset(("stop", "length"))
SUCCESSFUL_TGI_FINISH = frozenset(("length", "eos_token", "stop_sequence"))
MILLISECONDS_PER_SECOND = 1000


def count(value: object, name: str) -> int:
    """Native counters must be integers; bools and numerical strings are not counts."""
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        refuse(f"invalid native {name}")
    return value


@dataclass
class NativeTiming:
    start: float
    output_cap: int
    first_visible: float | None = None
    first_native: float | None = None
    last_native: float | None = None
    first_batch: int = 0
    output_ids: int = 0
    ids_present: bool = False
    ids_missing: bool = False

    def output(self, size: int, arrived: float) -> None:
        self.ids_present = True
        if not size:
            return
        self.output_ids += size
        if self.output_ids > self.output_cap:
            refuse("native tokens exceed requested output cap")
        if self.first_native is None:
            self.first_native = arrived
        if self.first_native == arrived:
            self.first_batch += size
        self.last_native = arrived

    def visible(self, text: str, arrived: float, callback: Callable[[], None]) -> None:
        if text and self.first_visible is None:
            self.first_visible = arrived
            callback()

    def observation(
        self, output: int, prompt: int | None, cache: int | None, end: float
    ) -> GenerationObservation:
        if output > self.output_cap:
            refuse("final native count exceeds requested output cap")
        if self.ids_present and self.output_ids != output:
            refuse("native token coverage disagrees with final count")
        interval = None
        if (
            self.ids_present
            and not self.ids_missing
            and self.first_batch == 1
            and output >= 2
            and self.first_native is not None
            and self.last_native is not None
            and self.last_native > self.first_native
        ):
            interval = self.last_native - self.first_native
        tpot = interval * MILLISECONDS_PER_SECOND / (output - 1) if interval is not None else None
        native = {
            "tokens_generated": output,
            "prompt_tokens": prompt,
            "cached_prompt_tokens": cache,
            "throughput_tps": (output - 1) / interval if interval is not None else None,
            "ttft_ms": (self.first_visible - self.start) * MILLISECONDS_PER_SECOND
            if self.first_visible is not None
            else None,
            "total_duration_ms": (end - self.start) * MILLISECONDS_PER_SECOND,
            "prompt_eval_duration_ms": None,
            "eval_duration_ms": interval * MILLISECONDS_PER_SECOND
            if interval is not None
            else None,
            "ttft_basis": "client-stream-first-content"
            if self.first_visible is not None
            else "unknown",
        }
        return GenerationObservation(
            native, tpot, CLIENT_NATIVE_TPOT_BASIS if tpot is not None else "unavailable"
        )


def usage_counts(value: dict) -> tuple[int, int, int | None]:
    output = count(value.get("completion_tokens"), "output count")
    prompt = count(value.get("prompt_tokens"), "prompt count")
    if "total_tokens" in value and count(value["total_tokens"], "total count") != output + prompt:
        refuse("inconsistent native total count")
    details = value.get("prompt_tokens_details")
    if details is not None and type(details) is not dict:
        refuse("invalid native prompt details")
    caches = [
        item
        for item in (value.get("cached_tokens"), (details or {}).get("cached_tokens"))
        if item is not None
    ]
    cache = count(caches[0], "cached prompt count") if caches else None
    if cache is not None and (
        cache > prompt or any(count(item, "cached prompt count") != cache for item in caches)
    ):
        refuse("inconsistent native cached prompt count")
    return output, prompt, cache


async def observe_openai(
    client: httpx.AsyncClient,
    url: str,
    payload: dict,
    clock: Callable[[], float],
    timeout: float,
    callback: Callable[[], None],
) -> GenerationObservation:
    """One completion choice, native delta IDs, successful finish, final usage and DONE."""
    timing = NativeTiming(clock(), count(payload.get("max_tokens"), "requested output cap"))
    finish = done = False
    usage: tuple[int, int, int | None] | None = None
    body = {
        **payload,
        "stream": True,
        "n": 1,
        "echo": False,
        "return_token_ids": True,
        "stream_options": {"include_usage": True},
    }
    async with open_frames(client, url, body, clock, timeout) as incoming:
        async for frame in incoming:
            if done:
                refuse("data after terminal DONE")
            if frame.done:
                if not finish or usage is None:
                    refuse("DONE without successful finish and final usage")
                done = True
                continue
            value = frame.value
            assert value is not None
            if "error" in value or "error_type" in value:
                refuse("in-band generation error")
            choices = value.get("choices")
            if type(choices) is not list:
                refuse("invalid completion choices")
            reported = value.get("usage")
            if reported is not None:
                if choices or not finish or usage is not None or type(reported) is not dict:
                    refuse("unexpected final usage")
                usage = usage_counts(reported)
                continue
            if len(choices) != 1 or finish or usage is not None:
                refuse("unexpected completion choice population")
            item = choices[0]
            if type(item) is not dict or type(item.get("index")) is not int or item["index"] != 0:
                refuse("unexpected completion choice index")
            text = item.get("text")
            if type(text) is not str:
                refuse("invalid completion text field")
            ids = item.get("token_ids")
            if ids is None:
                timing.ids_missing = True
            elif type(ids) is not list or any(type(ident) is not int or ident < 0 for ident in ids):
                refuse("invalid native output IDs")
            else:
                timing.output(len(ids), frame.arrived_s)
            timing.visible(text, frame.arrived_s, callback)
            reason = item.get("finish_reason")
            if reason is not None:
                if type(reason) is not str or reason not in SUCCESSFUL_OPENAI_FINISH:
                    refuse("unsuccessful completion finish")
                finish = True
    if not done or usage is None:
        refuse("incomplete completion transport")
    output, prompt, cache = usage
    return timing.observation(output, prompt, cache, clock())


async def observe_tgi(
    client: httpx.AsyncClient,
    url: str,
    payload: dict,
    clock: Callable[[], float],
    timeout: float,
    callback: Callable[[], None],
) -> GenerationObservation:
    """Each TGI event carries one native token; final details plus normal EOF qualify it."""
    timing = NativeTiming(
        clock(), count(payload["parameters"].get("max_new_tokens"), "requested output cap")
    )
    terminal: tuple[int, int | None] | None = None
    async with open_frames(client, url, payload, clock, timeout) as incoming:
        async for frame in incoming:
            if frame.done or terminal is not None:
                refuse("unexpected data after TGI terminal details")
            value = frame.value
            assert value is not None
            if "error" in value or "error_type" in value:
                refuse("in-band generation error")
            token = value.get("token")
            if type(token) is not dict:
                refuse("missing native TGI token")
            count(token.get("id"), "token ID")
            text, special = token.get("text"), token.get("special")
            if type(text) is not str or type(special) is not bool:
                refuse("invalid native TGI token")
            timing.output(1, frame.arrived_s)
            if not special:
                timing.visible(text, frame.arrived_s, callback)
            details = value.get("details")
            if details is not None:
                if (
                    type(details) is not dict
                    or type(details.get("finish_reason")) is not str
                    or details["finish_reason"] not in SUCCESSFUL_TGI_FINISH
                ):
                    refuse("invalid TGI final details")
                output = count(details.get("generated_tokens"), "output count")
                prompt = (
                    count(details["input_length"], "prompt count")
                    if details.get("input_length") is not None
                    else None
                )
                terminal = output, prompt
    if terminal is None:
        refuse("missing TGI final details")
    return timing.observation(*terminal, None, clock())


def legacy_metrics(observed: GenerationObservation) -> RunMetrics:
    """Legacy bench requires a rate; trace can retain valid rate-unavailable completions."""
    native = observed.native
    if observed.mean_tpot_ms is None or native["ttft_ms"] is None:
        refuse("decode rate unavailable: native output timing needs distinct arrivals")
    return RunMetrics(
        tokens_generated=native["tokens_generated"],
        throughput_tps=native["throughput_tps"],
        ttft_ms=native["ttft_ms"],
        total_duration_ms=native["total_duration_ms"],
        prompt_eval_duration_ms=native["ttft_ms"],
        eval_duration_ms=native["eval_duration_ms"],
        prompt_tokens=native["prompt_tokens"],
        cached_prompt_tokens=native["cached_prompt_tokens"],
        ttft_basis=native["ttft_basis"],
    )
