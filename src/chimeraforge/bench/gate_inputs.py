"""Bounded held benchmark bytes and recalculated native sample populations."""

from __future__ import annotations

import copy
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path

from chimeraforge.bench.metrics import BENCHMARK_WALL_BASIS, RunMetrics, aggregate_runs
from chimeraforge.bench.plan import PlanBenchmark
from chimeraforge.bench.serving import safe_observation
from chimeraforge.planner.replay import digest

MAX_RECEIPT_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 32 * 1024 * 1024
MAX_SAMPLES = 1000
MAX_TOKEN_COUNT = 2**31 - 1
MAX_POLICY_BYTES = 64 * 1024
# Float roundoff only for recalculated native arithmetic, never types/counts/identity.
SERIALIZATION_ROUNDOFF = 1e-12
WALL_BASIS = BENCHMARK_WALL_BASIS
ENVELOPE_KEYS = {
    "schema_version",
    "kind",
    "created_at",
    "plan",
    "execution",
    "measurement",
    "binding",
    "audit",
    "status",
    "configuration_status",
    "exit_code",
    "limits",
    "fingerprint",
}


def fail(message: str) -> None:
    from chimeraforge.api import PlanError

    raise PlanError(f"invalid regression gate input: {message}")


def finite(value: object, *, minimum: float | None = None) -> bool:
    try:
        return (
            type(value) in (int, float)
            and math.isfinite(value)
            and (minimum is None or value >= minimum)
        )
    except OverflowError:
        return False


def count(value: object, *, minimum: int = 0) -> bool:
    return type(value) is int and minimum <= value <= MAX_SAMPLES


def sha(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )


def _finite_float(text: str) -> float:
    value = float(text)
    if not math.isfinite(value):
        fail("nonfinite JSON number")
    return value


def held_json(source: object, limit: int) -> tuple[dict, bytes, Path | None]:
    """Read once and reject duplicate/nonfinite JSON, including public typed snapshots."""
    from chimeraforge.api import PlanError, _unique_object
    from chimeraforge.plan_bundle import _read

    path = None
    try:
        if isinstance(source, PlanBenchmark):
            source = source.to_dict()
        if isinstance(source, (str, Path)):
            path = Path(source).absolute()
            raw = _read(path, limit)
        elif type(source) is dict:
            raw = json.dumps(source, allow_nan=False).encode()
        else:
            fail("expected a receipt object or JSON file")
        if not 0 < len(raw) <= limit:
            fail("JSON exceeds byte limit")
        data = json.loads(
            raw,
            object_pairs_hook=_unique_object,
            parse_constant=lambda _: fail("nonfinite JSON"),
            parse_float=_finite_float,
        )
        if type(data) is not dict:
            fail("JSON root must be an object")
        return data, raw, path
    except PlanError:
        raise
    except (OSError, ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise PlanError("invalid regression gate JSON") from exc


def _equal_numbers(actual: object, expected: object) -> bool:
    """Only derived float arithmetic admits serialization-scale roundoff."""
    if type(expected) is dict:
        return (
            type(actual) is dict
            and set(actual) == set(expected)
            and all(_equal_numbers(actual[key], value) for key, value in expected.items())
        )
    if type(expected) is int:
        return type(actual) is int and actual == expected
    return (
        finite(actual)
        and finite(expected)
        and math.isclose(
            actual, expected, rel_tol=SERIALIZATION_ROUNDOFF, abs_tol=SERIALIZATION_ROUNDOFF
        )
    )


def samples(measurement: dict) -> list[RunMetrics]:
    rows = measurement.get("individual_runs")
    if type(rows) is not list or not 1 <= len(rows) <= MAX_SAMPLES:
        fail("native sample population needs 1-1000 rows")
    result = []
    names = set(RunMetrics.__annotations__)
    required = names - {"prompt_tokens", "cached_prompt_tokens", "ttft_basis"}
    for row in rows:
        if type(row) is not dict or not required <= set(row) <= names:
            fail("malformed native sample")
        if (
            type(row["tokens_generated"]) is not int
            or not 0 <= row["tokens_generated"] <= MAX_TOKEN_COUNT
        ):
            fail("output tokens must be integer counts")
        for name in (
            "throughput_tps",
            "total_duration_ms",
            "prompt_eval_duration_ms",
            "eval_duration_ms",
        ):
            if not finite(row[name], minimum=0):
                fail("native rates/durations must be finite nonnegative numbers")
        if not finite(row["ttft_ms"]):
            fail("TTFT must be finite; a native negative sentinel remains unavailable")
        for name in ("prompt_tokens", "cached_prompt_tokens"):
            if row.get(name) is not None and (
                type(row[name]) is not int or not 0 <= row[name] <= MAX_TOKEN_COUNT
            ):
                fail("observed token lengths must be nonnegative integer counts")
        if (
            row.get("cached_prompt_tokens") is not None
            and row.get("prompt_tokens") is not None
            and row["cached_prompt_tokens"] > row["prompt_tokens"]
        ):
            fail("cached tokens exceed prompt tokens")
        if "ttft_basis" in row and type(row["ttft_basis"]) is not str:
            fail("timing basis must be text")
        result.append(RunMetrics(**copy.deepcopy(row)))
    if not _equal_numbers(measurement.get("aggregate"), asdict(aggregate_runs(result))):
        fail("stored aggregate disagrees with raw samples")
    if not count(measurement.get("runs"), minimum=1) or measurement["runs"] < len(rows):
        fail("requested measurement count disagrees with samples")
    return result


def load_receipt(source: object) -> dict:
    data, raw, path = held_json(source, MAX_RECEIPT_BYTES)
    legacy = "kind" not in data
    if legacy:
        measurement = data
        execution = None
    else:
        if (
            set(data) != ENVELOPE_KEYS
            or type(data["schema_version"]) is not int
            or data["schema_version"] != 1
            or data["kind"] != "chimeraforge.plan-benchmark"
        ):
            fail("unsupported benchmark envelope")
        if (
            not sha(data["fingerprint"])
            or digest({k: v for k, v in data.items() if k != "fingerprint"}) != data["fingerprint"]
        ):
            fail("benchmark fingerprint mismatch")
        measurement, execution = data["measurement"], data["execution"]
        if type(execution) is not dict:
            fail("execution must be an object")
    if type(measurement) is not dict:
        fail("measurement must be an object")
    rows = samples(measurement)
    for name in ("backend", "model", "workload"):
        if type(measurement.get(name)) is not str or not measurement[name]:
            fail("measurement identity/workload is missing")
    if not legacy:
        for name in ("requested_count", "successful_count", "failed_count"):
            if not count(execution.get(name), minimum=1 if name == "requested_count" else 0):
                fail("execution counts must be integers")
        if (
            execution["successful_count"] != len(rows)
            or execution["requested_count"]
            != execution["successful_count"] + execution["failed_count"]
            or execution["requested_count"] != measurement["runs"]
        ):
            fail("execution population disagrees with native samples")
        if execution.get("individual_runs") != measurement["individual_runs"]:
            fail("two stored native sample populations disagree")
        if not finite(execution.get("elapsed_seconds"), minimum=0):
            fail("elapsed seconds must be finite nonnegative")
        request = execution.get("request")
        if type(request) is not dict or not sha(request.get("prompt_sha256")):
            fail("request needs prompt SHA256")
        if (
            request.get("workload") not in ("single", "batch", "server")
            or request["workload"] != measurement["workload"]
            or not count(request.get("requested_count"), minimum=1)
            or request["requested_count"] != execution["requested_count"]
            or type(request.get("concurrency")) is not int
            or not 1 <= request["concurrency"] <= MAX_SAMPLES
            or type(request.get("options")) is not dict
        ):
            fail("applied request profile is malformed")
        if request["workload"] == "single" and request["concurrency"] != 1:
            fail("single workload must apply concurrency one")
        arrival = request.get("arrival_rate")
        if (
            (request["workload"] == "server" and (not finite(arrival, minimum=0) or arrival <= 0))
            or request["workload"] != "server"
            and arrival is not None
        ):
            fail("arrival rate disagrees with applied workload")
        for phase in ("serving_before", "serving_after"):
            if type(execution.get(phase)) is not dict:
                fail("serving observations must be objects")
        before, after = [
            safe_observation(execution[key]) for key in ("serving_before", "serving_after")
        ]
        engine = after.get("backend")
        if before.get("backend") == engine:
            for row in rows:
                supported = (
                    (engine == "ollama" and row.ttft_basis == "server-prefill-duration")
                    or engine in ("vllm", "tgi", "sglang")
                    and row.ttft_basis == "client-stream-first-content"
                )
                if (
                    supported
                    and row.ttft_ms > 0
                    and not math.isclose(
                        row.ttft_ms,
                        row.prompt_eval_duration_ms,
                        rel_tol=SERIALIZATION_ROUNDOFF,
                        abs_tol=SERIALIZATION_ROUNDOFF,
                    )
                ):
                    fail("native TTFT disagrees with its supported prefill alias")
    return {
        "measurement": measurement,
        "execution": execution,
        "samples": rows,
        "legacy": legacy,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "fingerprint": data.get("fingerprint"),
        "size_bytes": len(raw),
        "path": path,
    }
