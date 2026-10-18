"""Held trace snapshots and recalculated queue-inclusive populations."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path

from chimeraforge.bench.gate_inputs import (
    MAX_RECEIPT_BYTES,
    MAX_TOKEN_COUNT,
    SERIALIZATION_ROUNDOFF,
    fail,
    finite,
    held_json,
    sha,
)
from chimeraforge.bench.trace import (
    BUILTIN_TPOT_BASES,
    NATIVE_FIELDS,
    TraceReplay,
    _qualify,
    _timing,
)
from chimeraforge.bench.trace_workload import (
    MAX_CONCURRENCY,
    MAX_OUTPUT_TOKENS,
    MAX_PROMPT_BYTES,
    MAX_TIMEOUT_SECONDS,
    MAX_TRACE_REQUESTS,
    REQUEST_ID,
)
from chimeraforge.planner.replay import digest

ENVELOPE = {
    "schema_version",
    "created_at",
    "tool",
    "model",
    "backend",
    "endpoint",
    "workload",
    "requests",
    "targets",
    "execution",
    "clock",
    "timing_bases",
    "deadline_scope",
    "goodput",
    "serving_before",
    "serving_after",
    "serving_stability",
    "resource_cleanup",
    "stop_reason",
    "error",
    "exit_code",
    "performance",
    "limits",
    "fingerprint",
}
STATES = ("completed", "failed", "partial", "cancelled", "not_started")
TIMES = ("scheduled_s", "arrival_s", "start_s", "first_output_s", "terminal_s")
TARGETS = ("latency_ms", "first_output_ms", "tpot_ms")
TIMING_BASES = {
    "latency_ms": "scheduled-arrival-to-client-terminal",
    "first_output_ms": "scheduled-arrival-to-client-first-output",
    "tpot_ms": "per-request explicitly named mean decode basis; not every-token latency",
}
CLOCK_BASIS = "client time.perf_counter monotonic offsets in seconds"
HORIZON_BASIS = "origin to max(last planned arrival, observed terminal/stop)"


def trace_count(value: object, maximum: int = MAX_TRACE_REQUESTS) -> bool:
    return type(value) is int and 0 <= value <= maximum


def held_trace_json(source: object, limit: int) -> tuple[dict, bytes, Path | None]:
    """Use the shared strict reader without reflecting arbitrary JSON field names."""
    from chimeraforge.api import PlanError

    try:
        if isinstance(source, TraceReplay):
            source = source.to_dict()
        return held_json(source, limit)
    except (PlanError, ValueError, TypeError, RecursionError):
        raise PlanError("invalid trace gate input: malformed bounded JSON") from None


def same_number(actual: object, expected: object) -> bool:
    return (
        actual is None
        if expected is None
        else (
            finite(actual)
            and finite(expected)
            and math.isclose(
                actual, expected, rel_tol=SERIALIZATION_ROUNDOFF, abs_tol=SERIALIZATION_ROUNDOFF
            )
        )
    )


def _error(value: object) -> None:
    if value is not None and (
        type(value) is not dict
        or set(value) != {"stage", "type"}
        or type(value["stage"]) is not str
        or value["stage"]
        not in {
            "generation",
            "preflight",
            "metadata_before",
            "scheduled_replay",
            "metadata_after",
            "cleanup",
        }
        or type(value["type"]) is not str
        or value["type"]
        not in {"TimeoutError", "HTTPError", "ValueError", "RuntimeError", "BackendError"}
    ):
        fail("trace errors must be categorical producer observations")


def _native(row: dict, backend: str) -> None:
    native = row["native"]
    if type(native) is not dict or not set(NATIVE_FIELDS) <= set(native) <= set(NATIVE_FIELDS) | {
        "ttft_basis"
    }:
        fail("unsupported trace native fields")
    for name in NATIVE_FIELDS:
        value = native[name]
        if value is not None and not finite(value, minimum=0):
            fail("trace native observations must be finite nonnegative or unknown")
        if (
            name in {"tokens_generated", "prompt_tokens", "cached_prompt_tokens"}
            and value is not None
            and not trace_count(value, MAX_TOKEN_COUNT)
        ):
            fail("trace native token counts must be bounded integers")
    if (
        native["cached_prompt_tokens"] is not None
        and native["prompt_tokens"] is not None
        and native["cached_prompt_tokens"] > native["prompt_tokens"]
    ):
        fail("trace cached tokens exceed prompt population")
    basis, mean = row["mean_tpot_basis"], row["mean_tpot_ms"]
    if (
        type(basis) is not str
        or basis not in BUILTIN_TPOT_BASES | {"unavailable"}
        or mean is not None
        and (not finite(mean, minimum=0) or mean <= 0)
    ):
        fail("unsupported trace mean timing observation")
    expected_backend = (
        "ollama"
        if basis == "server-decode-duration/output-token-count"
        else {"vllm", "tgi", "sglang"}
    )
    if basis != "unavailable" and (
        backend != expected_backend
        if type(expected_backend) is str
        else backend not in expected_backend
    ):
        fail("trace mean timing basis contradicts its serving backend")
    if basis == "unavailable" and mean is not None:
        fail("unavailable trace mean cannot contain a value")
    count, elapsed = native["tokens_generated"], native["eval_duration_ms"]
    denominator = (
        count
        if basis == "server-decode-duration/output-token-count"
        else count - 1
        if count is not None
        else None
    )
    if mean is not None and (
        denominator is None
        or denominator <= 0
        or elapsed is None
        or elapsed <= 0
        or not same_number(mean, elapsed / denominator)
    ):
        fail("trace mean disagrees with native count/interval arithmetic")
    ttft_basis = native.get("ttft_basis")
    if ttft_basis is not None and (
        type(ttft_basis) is not str
        or ttft_basis not in {"server-prefill-duration", "client-stream-first-content", "unknown"}
    ):
        fail("unknown trace native timing basis")
    if (
        ttft_basis == "server-prefill-duration"
        and backend == "ollama"
        and native["ttft_ms"] is not None
        and native["prompt_eval_duration_ms"] is not None
        and not same_number(native["ttft_ms"], native["prompt_eval_duration_ms"])
    ):
        fail("trace prefill observations disagree")
    divisor = (
        count
        if backend == "ollama" and ttft_basis == "server-prefill-duration"
        else count - 1
        if count is not None
        and backend in {"vllm", "tgi", "sglang"}
        and ttft_basis == "client-stream-first-content"
        else None
    )
    rate = native["throughput_tps"]
    if (
        rate is not None
        and divisor is not None
        and divisor > 0
        and elapsed is not None
        and elapsed > 0
        and not same_number(rate, 1000 * divisor / elapsed)
    ):
        fail("trace decode rate disagrees with native count/interval")


def validate_descriptor(descriptor: object, seen: set[str]) -> None:
    """Validate declared descriptors even when a campaign has no native receipt."""
    if type(descriptor) is not dict or set(descriptor) != {
        "request_id",
        "prompt_sha256",
        "prompt_bytes",
        "max_output_tokens",
        "arrival_offset_s",
    }:
        fail("unsupported trace request descriptor")
    ident = descriptor["request_id"]
    if type(ident) is not str or not REQUEST_ID.fullmatch(ident) or ident in seen:
        fail("trace request IDs must be valid and unique")
    seen.add(ident)
    if (
        not sha(descriptor["prompt_sha256"])
        or not trace_count(descriptor["prompt_bytes"], MAX_PROMPT_BYTES)
        or descriptor["prompt_bytes"] <= 0
        or not trace_count(descriptor["max_output_tokens"], MAX_OUTPUT_TOKENS)
        or descriptor["max_output_tokens"] <= 0
        or not finite(descriptor["arrival_offset_s"], minimum=0)
        or descriptor["arrival_offset_s"] > MAX_TIMEOUT_SECONDS
    ):
        fail("trace descriptor counts/hash/schedule are invalid")


def _row(row: object, backend: str, targets: dict, seen: set[str]) -> None:
    names = {
        "descriptor",
        "state",
        "times",
        "native",
        "error",
        "mean_tpot_ms",
        "mean_tpot_basis",
        "timing",
        "slo",
        "output_cap_state",
    }
    if type(row) is not dict or set(row) != names or row["state"] not in STATES:
        fail("unsupported trace request row")
    descriptor = row["descriptor"]
    validate_descriptor(descriptor, seen)
    times = row["times"]
    if (
        type(times) is not dict
        or set(times) != set(TIMES)
        or any(value is not None and not finite(value, minimum=0) for value in times.values())
        or digest(times["scheduled_s"]) != digest(descriptor["arrival_offset_s"])
    ):
        fail("trace relative timestamps must match the applied schedule")
    arrival, start, first, terminal = [times[key] for key in TIMES[1:]]
    if (
        arrival is not None
        and arrival < times["scheduled_s"]
        or start is not None
        and (arrival is None or start < arrival)
        or terminal is not None
        and start is not None
        and terminal < start
        or first is not None
        and (start is None or terminal is None or not start <= first <= terminal)
    ):
        fail("trace timestamp chronology is inconsistent")
    if (
        row["state"] == "completed"
        and any(value is None for value in (arrival, start, terminal))
        or row["state"] == "not_started"
        and any(value is not None for value in (arrival, start, first, terminal))
        or row["state"] == "partial"
        and first is None
        or row["state"] == "failed"
        and first is not None
    ):
        fail("trace state contradicts observed lifecycle")
    _error(row["error"])
    if row["state"] in ("failed", "partial"):
        if row["error"] is None or row["error"]["stage"] != "generation":
            fail("failed/partial trace requests need categorical generation errors")
    elif row["error"] is not None:
        fail("completed/cancelled/unstarted trace requests cannot contain generation errors")
    _native(row, backend)
    expected = _timing(row)
    if (
        type(row["timing"]) is not dict
        or set(row["timing"]) != set(expected)
        or any(not same_number(row["timing"][key], value) for key, value in expected.items())
    ):
        fail("trace timing summary disagrees with relative observations")
    if type(row["slo"]) is not dict or row["slo"] != _qualify(row, targets):
        fail("trace SLO states disagree with observations")
    count = row["native"]["tokens_generated"]
    cap_state = (
        "unknown"
        if count is None
        else "within_cap"
        if count <= descriptor["max_output_tokens"]
        else "exceeded"
    )
    if row["output_cap_state"] != cap_state:
        fail("trace output-cap state disagrees with observed count")


def load_trace(source: object, *, limit: int = MAX_RECEIPT_BYTES) -> dict:
    protected = source._protected_paths if isinstance(source, TraceReplay) else ()
    data, raw, path = held_trace_json(source, limit)
    if (
        set(data) != ENVELOPE
        or type(data["schema_version"]) is not int
        or data["schema_version"] != 1
        or not sha(data["fingerprint"])
        or digest({k: v for k, v in data.items() if k != "fingerprint"}) != data["fingerprint"]
    ):
        fail("unsupported trace envelope or fingerprint")
    if any(
        type(data[key]) is not str or not data[key].strip() or len(data[key]) > 512
        for key in ("model", "backend")
    ):
        fail("trace serving identity is missing")
    if (
        type(data["created_at"]) is not str
        or len(data["created_at"]) > 128
        or type(data["tool"]) is not dict
        or set(data["tool"]) != {"name", "version"}
        or data["tool"]["name"] != "chimeraforge"
        or type(data["tool"]["version"]) is not str
        or not 0 < len(data["tool"]["version"]) <= 128
        or data["endpoint"] is not None
        and (type(data["endpoint"]) is not str or len(data["endpoint"]) > 4096)
        or type(data["limits"]) is not str
        or len(data["limits"]) > 4096
        or data["deadline_scope"]
        != "scheduled replay only; preflight/metadata separately bounded, cleanup cooperative"
    ):
        fail("trace producer metadata shape is unsupported")
    workload, rows, targets = data["workload"], data["requests"], data["targets"]
    if (
        type(workload) is not dict
        or set(workload) != {"canonical_sha256", "raw_sha256"}
        or not sha(workload["canonical_sha256"])
        or workload["raw_sha256"] is not None
        and not sha(workload["raw_sha256"])
    ):
        fail("trace workload bindings are invalid")
    if (
        type(rows) is not list
        or not 1 <= len(rows) <= MAX_TRACE_REQUESTS
        or type(targets) is not dict
        or set(targets) != set(TARGETS)
        or any(
            value is not None and (not finite(value, minimum=0) or value <= 0)
            for value in targets.values()
        )
    ):
        fail("trace needs 1-1024 requests and supported positive targets")
    seen: set[str] = set()
    for row in rows:
        _row(row, data["backend"], targets, seen)
    execution = data["execution"]
    counts = {state: sum(row["state"] == state for row in rows) for state in STATES}
    expected_counts = {
        "planned": len(rows),
        "attempted": sum(row["times"]["start_s"] is not None for row in rows),
        **counts,
    }
    if (
        type(execution) is not dict
        or set(execution)
        != set(expected_counts)
        | {"concurrency", "request_timeout_seconds", "trace_timeout_seconds", "elapsed_seconds"}
        or any(
            not trace_count(execution[key]) or execution[key] != value
            for key, value in expected_counts.items()
        )
    ):
        fail("trace execution counts disagree with retained request population")
    if (
        not trace_count(execution["concurrency"], MAX_CONCURRENCY)
        or execution["concurrency"] < 1
        or any(
            not finite(execution[key], minimum=0) or not 0 < execution[key] <= MAX_TIMEOUT_SECONDS
            for key in ("request_timeout_seconds", "trace_timeout_seconds")
        )
    ):
        fail("trace applied concurrency/timeouts are invalid")
    intervals = []
    for row in rows:
        start, terminal = row["times"]["start_s"], row["times"]["terminal_s"]
        if start is not None and terminal is not None and start < terminal:
            intervals.extend(((start, 1), (terminal, -1)))
    active = 0
    # Half-open intervals release before admission at ties; zero durations need no slot.
    for _, change in sorted(intervals):
        active += change
        if active > execution["concurrency"]:
            fail("trace execution intervals exceed applied concurrency")
    planned = max(row["descriptor"]["arrival_offset_s"] for row in rows)
    if planned > execution["trace_timeout_seconds"]:
        fail("trace schedule exceeds applied trace timeout")
    clock = data["clock"]
    if (
        type(clock) is not dict
        or set(clock) != {"basis", "origin", "resolution_seconds"}
        or clock["basis"] != CLOCK_BASIS
        or clock["origin"] is not None
        and not finite(clock["origin"], minimum=0)
        or not finite(clock["resolution_seconds"], minimum=0)
        or clock["resolution_seconds"] <= 0
        or data["timing_bases"] != TIMING_BASES
    ):
        fail("trace monotonic clock/timing basis is unsupported")
    elapsed = execution["elapsed_seconds"]
    if (
        elapsed is not None
        and not finite(elapsed, minimum=0)
        or clock["origin"] is not None
        and elapsed is None
    ):
        fail("trace elapsed primitive must be finite nonnegative when observed")
    if elapsed is not None and any(
        row["times"]["terminal_s"] is not None and row["times"]["terminal_s"] > elapsed
        for row in rows
    ):
        fail("trace terminal cannot exceed drained elapsed observation")
    horizon = max(elapsed, planned) if clock["origin"] is not None and elapsed is not None else None
    requested = any(value is not None for value in targets.values())
    qualified = sum(row["slo"]["joint"] == "pass" for row in rows)
    expected_goodput = {
        "qualification": "not_requested"
        if not requested
        else "observed_targets"
        if clock["origin"] is not None
        else "unavailable",
        "qualified_requests": qualified,
        "horizon_seconds": horizon,
        "planned_horizon_seconds": planned,
        "horizon_basis": HORIZON_BASIS,
        "joint_outcomes": {
            state: sum(row["slo"]["joint"] == state for row in rows)
            for state in ("pass", "breach", "unknown", "not_completed", "not_requested")
        },
        "requests_per_second": qualified / horizon
        if requested and horizon is not None and horizon > 0
        else None,
    }
    goodput = data["goodput"]
    if (
        type(goodput) is not dict
        or set(goodput) != set(expected_goodput)
        or any(
            not same_number(goodput[key], expected_goodput[key])
            for key in ("horizon_seconds", "planned_horizon_seconds", "requests_per_second")
        )
        or any(
            type(goodput[key]) is not int or goodput[key] != expected_goodput[key]
            for key in ("qualified_requests",)
        )
        or type(goodput["joint_outcomes"]) is not dict
        or set(goodput["joint_outcomes"]) != set(expected_goodput["joint_outcomes"])
        or any(
            not trace_count(value) or value != expected_goodput["joint_outcomes"][key]
            for key, value in goodput["joint_outcomes"].items()
        )
        or any(goodput[key] != expected_goodput[key] for key in ("qualification", "horizon_basis"))
    ):
        fail("trace goodput summary disagrees with full population/drained horizon")
    _error(data["error"])
    if (
        data["stop_reason"] not in (None, "cancelled", "trace_deadline")
        or type(data["exit_code"]) is not int
        or data["exit_code"]
        != (
            0
            if counts["completed"] == len(rows)
            and data["error"] is None
            and data["stop_reason"] is None
            else 1
        )
    ):
        fail("trace producer outcome disagrees with completion/failure state")
    for key in ("serving_before", "serving_after"):
        if data[key] is not None and type(data[key]) is not dict:
            fail("trace serving observations must be objects or unknown")
    from chimeraforge.bench.serving import safe_observation
    from chimeraforge.bench.serving_binding import serving_stability

    for key in ("serving_before", "serving_after"):
        if data[key] is not None and digest(data[key]) != digest(safe_observation(data[key])):
            fail("trace serving observations must use supported projected fields")
    if digest(data["serving_stability"]) != digest(
        serving_stability(data["serving_before"] or {}, data["serving_after"] or {})
    ):
        fail("trace serving stability summary disagrees with held observations")
    if data["performance"] != {
        "state": "observed_client_workload" if clock["origin"] is not None else "unavailable",
        "gpu_qualification": "unverified",
        "served_file_authentication": "unverified",
    }:
        fail("trace performance scope is unsupported")
    cleanup = data["resource_cleanup"]
    if (
        type(cleanup) is not dict
        or not set(cleanup) <= {"state"}
        or cleanup.get("state") not in (None, "started", "completed", "incomplete")
    ):
        fail("trace cleanup must be a supported categorical observation")
    return {
        "data": data,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
        "path": path,
        "protected_paths": tuple(protected),
        "fingerprint": data["fingerprint"],
        "execution": execution,
        "goodput": expected_goodput,
    }
