"""Closed, bounded input contract for scheduled request replay."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
import re

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


@dataclass(frozen=True)
class TraceRequest:
    """One explicitly scheduled prompt and requested output cap."""

    request_id: str
    prompt: str = field(repr=False)
    max_output_tokens: int
    arrival_offset_s: float


@dataclass(frozen=True)
class TraceSLO:
    """Client queue-inclusive targets and an explicitly labeled mean decode target."""

    latency_ms: float | None = None
    first_output_ms: float | None = None
    tpot_ms: float | None = None


def number(value: object, *, positive: bool = False) -> bool:
    try:
        return (
            type(value) in (int, float)
            and math.isfinite(value)
            and (value > 0 if positive else value >= 0)
        )
    except OverflowError:
        return False


def load_workload(
    source: list[TraceRequest] | str | Path,
) -> tuple[list[TraceRequest], dict, tuple[Path, ...]]:
    from chimeraforge.api import PlanError, _unique_object
    from chimeraforge.plan_bundle import _read

    protected = ()
    raw_sha = None
    try:
        if type(source) is list:
            rows = list(source)
        else:
            path = Path(source).absolute()
            raw = _read(path, MAX_TRACE_BYTES)
            data = json.loads(raw, object_pairs_hook=_unique_object)
            if type(data) is not list or any(
                type(row) is not dict or set(row) != set(TraceRequest.__annotations__)
                for row in data
            ):
                raise PlanError("trace must be a list of exact request objects")
            rows = [TraceRequest(**row) for row in data]
            raw_sha = hashlib.sha256(raw).hexdigest()
            protected = (path,)
        if not 1 <= len(rows) <= MAX_TRACE_REQUESTS:
            raise PlanError(f"trace needs 1-{MAX_TRACE_REQUESTS} requests")
        seen = set()
        for row in rows:
            if type(row) is not TraceRequest:
                raise PlanError("trace needs typed requests")
            if type(row.request_id) is not str or not REQUEST_ID.fullmatch(row.request_id):
                raise PlanError(
                    "request IDs need 1-80 ASCII letters, digits, dots, underscores or hyphens"
                )
            if row.request_id in seen:
                raise PlanError("request IDs must be unique")
            seen.add(row.request_id)
            if (
                type(row.prompt) is not str
                or not row.prompt
                or len(row.prompt.encode()) > MAX_PROMPT_BYTES
            ):
                raise PlanError("each prompt must be nonempty and at most 64 KiB")
            if (
                type(row.max_output_tokens) is not int
                or not 1 <= row.max_output_tokens <= MAX_OUTPUT_TOKENS
            ):
                raise PlanError(f"output caps need 1-{MAX_OUTPUT_TOKENS} integer tokens")
            if not number(row.arrival_offset_s) or row.arrival_offset_s > MAX_TIMEOUT_SECONDS:
                raise PlanError("arrival offsets must be finite nonnegative seconds, at most 3600")
        canonical = [asdict(row) for row in rows]
        if len(json.dumps(canonical).encode()) > MAX_TRACE_BYTES:
            raise PlanError("trace exceeds 8 MiB")
        return rows, {"canonical_sha256": digest(canonical), "raw_sha256": raw_sha}, protected
    except PlanError:
        raise
    except (OSError, ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise PlanError("invalid trace input") from exc


def validate_options(
    rows: list[TraceRequest],
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


def descriptor(row: TraceRequest) -> dict:
    return {
        "request_id": row.request_id,
        "prompt_sha256": hashlib.sha256(row.prompt.encode()).hexdigest(),
        "prompt_bytes": len(row.prompt.encode()),
        "max_output_tokens": row.max_output_tokens,
        "arrival_offset_s": row.arrival_offset_s,
    }
