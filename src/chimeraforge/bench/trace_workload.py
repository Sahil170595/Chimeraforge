"""Closed, bounded input contract for scheduled request replay."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
import re
from typing import TypeAlias, cast

from chimeraforge.planner.replay import digest

MAX_TRACE_REQUESTS = 1024
MAX_TRACE_BYTES = 8 * 1024 * 1024
MAX_PROMPT_BYTES = 64 * 1024
MAX_OUTPUT_TOKENS = 32768
MAX_CONCURRENCY = 64
MAX_TIMEOUT_SECONDS = 3600
DEFAULT_REQUEST_TIMEOUT_SECONDS = 300
DEFAULT_TRACE_TIMEOUT_SECONDS = 600
REQUEST_ID = re.compile(r"[A-Za-z0-9._-]{1,80}\Z")
MAX_CHAT_MESSAGES = 128
CHAT_ROLES = frozenset(("system", "user", "assistant"))
CHAT_PROFILE = "native-text-chat-v1"
CHAT_DESCRIPTOR_FIELDS = {
    "request_id",
    "mode",
    "profile",
    "messages",
    "message_commitment_sha256",
    "max_output_tokens",
    "arrival_offset_s",
    "temperature",
}


@dataclass(frozen=True)
class TraceRequest:
    """One explicitly scheduled prompt and requested output cap."""

    request_id: str
    prompt: str = field(repr=False)
    max_output_tokens: int
    arrival_offset_s: float


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """One ordered plain-text role/content pair, without tool or media fields."""

    role: str
    content: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class ChatTraceRequest:
    """One independent static conversation history and explicit generation controls."""

    request_id: str
    messages: tuple[ChatMessage, ...] = field(repr=False)
    max_output_tokens: int
    arrival_offset_s: float
    temperature: float = 0.0
    mode: str = field(default="chat", init=False)


TraceInput: TypeAlias = TraceRequest | ChatTraceRequest
TraceSource: TypeAlias = list[TraceRequest] | list[ChatTraceRequest] | list[TraceInput] | str | Path


def chat_backend_supported(name: str) -> bool:
    from chimeraforge.bench.backends import BACKEND_REGISTRY
    from chimeraforge.bench.backends.base import Backend

    cls = BACKEND_REGISTRY.get(name)
    return (
        isinstance(cls, type)
        and issubclass(cls, Backend)
        and cls.chat_observed is not Backend.chat_observed
    )


@dataclass(frozen=True)
class TraceSLO:
    """Client queue-inclusive targets and an explicitly labeled mean decode target."""

    latency_ms: float | None = None
    first_output_ms: float | None = None
    tpot_ms: float | None = None


def number(value: object, *, positive: bool = False) -> bool:
    try:
        if type(value) not in (int, float):
            return False
        numeric = cast(int | float, value)
        return math.isfinite(numeric) and (numeric > 0 if positive else numeric >= 0)
    except OverflowError:
        return False


def load_workload(
    source: TraceSource,
) -> tuple[list[TraceInput], dict, tuple[Path, ...]]:
    from chimeraforge.api import PlanError, _unique_object
    from chimeraforge.plan_bundle import _read

    protected: tuple[Path, ...] = ()
    rows: list[TraceInput]
    raw_sha = None
    try:
        if type(source) is list:
            if not 1 <= len(source) <= MAX_TRACE_REQUESTS:
                raise PlanError(f"trace needs 1-{MAX_TRACE_REQUESTS} requests")
            rows = list(source)
        else:
            path = Path(cast(str | Path, source)).absolute()
            raw = _read(path, MAX_TRACE_BYTES)
            data = json.loads(raw, object_pairs_hook=_unique_object)
            if type(data) is not list or not 1 <= len(data) <= MAX_TRACE_REQUESTS:
                raise PlanError("trace must be a list of exact request objects")
            rows = []
            for item in data:
                if type(item) is not dict:
                    raise PlanError("trace needs exact request objects")
                if set(item) == set(TraceRequest.__annotations__):
                    rows.append(TraceRequest(**item))
                elif set(item) == set(ChatTraceRequest.__annotations__) and item["mode"] == "chat":
                    messages = item["messages"]
                    if type(messages) is not list or not 1 <= len(messages) <= MAX_CHAT_MESSAGES:
                        raise PlanError("chat needs 1-128 ordered messages")
                    if any(type(m) is not dict or set(m) != {"role", "content"} for m in messages):
                        raise PlanError("chat messages need exactly role and content")
                    rows.append(
                        ChatTraceRequest(
                            item["request_id"],
                            tuple(ChatMessage(**m) for m in messages),
                            item["max_output_tokens"],
                            item["arrival_offset_s"],
                            item["temperature"],
                        )
                    )
                else:
                    raise PlanError("trace needs closed prompt or explicit chat objects")
            raw_sha = hashlib.sha256(raw).hexdigest()
            protected = (path,)
        if not 1 <= len(rows) <= MAX_TRACE_REQUESTS:
            raise PlanError(f"trace needs 1-{MAX_TRACE_REQUESTS} requests")
        seen = set()
        for row in rows:
            if type(row) not in (TraceRequest, ChatTraceRequest):
                raise PlanError("trace needs typed requests")
            if type(row.request_id) is not str or not REQUEST_ID.fullmatch(row.request_id):
                raise PlanError(
                    "request IDs need 1-80 ASCII letters, digits, dots, underscores or hyphens"
                )
            if row.request_id in seen:
                raise PlanError("request IDs must be unique")
            seen.add(row.request_id)
            if isinstance(row, TraceRequest):
                if (
                    type(row.prompt) is not str
                    or not row.prompt
                    or len(row.prompt.encode()) > MAX_PROMPT_BYTES
                ):
                    raise PlanError("each prompt must be nonempty and at most 64 KiB")
            else:
                if (
                    row.mode != "chat"
                    or type(row.messages) is not tuple
                    or not 1 <= len(row.messages) <= MAX_CHAT_MESSAGES
                    or not number(row.temperature)
                    or row.temperature > 2
                ):
                    raise PlanError("invalid bounded chat settings")
                total = 0
                for message in row.messages:
                    if (
                        type(message) is not ChatMessage
                        or type(message.role) is not str
                        or message.role not in CHAT_ROLES
                        or type(message.content) is not str
                        or not message.content
                        or len(message.content) > MAX_PROMPT_BYTES
                    ):
                        raise PlanError("chat needs closed nonempty text messages")
                    total += len(message.content.encode("utf-8"))
                    if total > MAX_PROMPT_BYTES:
                        raise PlanError("chat content exceeds 64 KiB per request")
            if (
                type(row.max_output_tokens) is not int
                or not 1 <= row.max_output_tokens <= MAX_OUTPUT_TOKENS
            ):
                raise PlanError(f"output caps need 1-{MAX_OUTPUT_TOKENS} integer tokens")
            if not number(row.arrival_offset_s) or row.arrival_offset_s > MAX_TIMEOUT_SECONDS:
                raise PlanError("arrival offsets must be finite nonnegative seconds, at most 3600")
        canonical: list[dict] = []
        encoded_bytes = 2  # Existing JSON list representation, including separators.
        for row in rows:
            value = asdict(row)
            encoded_bytes += len(json.dumps(value).encode()) + (2 if canonical else 0)
            if encoded_bytes > MAX_TRACE_BYTES:
                raise PlanError("trace exceeds 8 MiB")
            canonical.append(value)
        return rows, {"canonical_sha256": digest(canonical), "raw_sha256": raw_sha}, protected
    except PlanError:
        raise
    except (OSError, ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise PlanError("invalid trace input") from exc


def validate_options(
    rows: list[TraceInput],
    model: str,
    backend: str,
    concurrency: int,
    request_timeout: float,
    trace_timeout: float,
    slos: TraceSLO,
    base_url: str | None,
) -> None:
    from urllib.parse import urlsplit
    from chimeraforge.api import PlanError

    if any(type(value) is not str or not value.strip() for value in (model, backend)):
        raise PlanError("model and backend need nonempty names")
    if any(type(row) is ChatTraceRequest for row in rows) and not chat_backend_supported(backend):
        raise PlanError("backend does not support native text chat")
    if type(concurrency) is not int or not 1 <= concurrency <= MAX_CONCURRENCY:
        raise PlanError(f"concurrency needs 1-{MAX_CONCURRENCY}")
    for value in (request_timeout, trace_timeout):
        if not number(value, positive=True) or value > MAX_TIMEOUT_SECONDS:
            raise PlanError("timeouts must be finite positive seconds, at most 3600")
    if max(row.arrival_offset_s for row in rows) > trace_timeout:
        raise PlanError("arrival offsets must fit the whole scheduled-trace timeout")
    if type(slos) is not TraceSLO or any(
        value is not None and not number(value, positive=True) for value in asdict(slos).values()
    ):
        raise PlanError("SLO targets must be finite positive milliseconds")
    if base_url is not None:
        try:
            parsed = urlsplit(base_url)
            if parsed.scheme not in ("http", "https") or not parsed.hostname:
                raise ValueError
            parsed.port
        except (ValueError, TypeError) as exc:
            raise PlanError("endpoint needs an HTTP(S) URL with a host") from exc
    if any(type(row) is ChatTraceRequest for row in rows):
        from chimeraforge.bench.gate_inputs import MAX_RECEIPT_BYTES

        descriptor_bytes = 0
        for row in rows:
            # Standalone pretty descriptors are a lower bound on the enclosing receipt.
            descriptor_bytes += len(
                json.dumps(descriptor(row), indent=2, allow_nan=False)
                .replace("\n", "\r\n")
                .encode("utf-8")
            )
            if descriptor_bytes > MAX_RECEIPT_BYTES:
                raise PlanError("chat descriptors exceed the native receipt byte limit")


def descriptor(row: TraceInput) -> dict:
    if isinstance(row, ChatTraceRequest):
        messages = [
            {
                "role": m.role,
                "content_sha256": hashlib.sha256(m.content.encode()).hexdigest(),
                "content_bytes": len(m.content.encode()),
            }
            for m in row.messages
        ]
        return {
            "request_id": row.request_id,
            "mode": "chat",
            "profile": CHAT_PROFILE,
            "messages": messages,
            "message_commitment_sha256": digest(messages),
            "max_output_tokens": row.max_output_tokens,
            "arrival_offset_s": row.arrival_offset_s,
            "temperature": row.temperature,
        }
    return {
        "request_id": row.request_id,
        "prompt_sha256": hashlib.sha256(row.prompt.encode()).hexdigest(),
        "prompt_bytes": len(row.prompt.encode()),
        "max_output_tokens": row.max_output_tokens,
        "arrival_offset_s": row.arrival_offset_s,
    }
