"""Closed public native projection and private recorded-options commitments."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, NoReturn, cast

from chimeraforge.bench.gate import FACTS, _fact, _metric
from chimeraforge.bench.gate_inputs import (
    MAX_RECEIPT_BYTES,
    MAX_SAMPLES,
    MAX_TOKEN_COUNT,
    WALL_BASIS,
    count,
    finite,
    load_receipt,
    sha,
    validate_population,
    validate_native_aliases,
)
from chimeraforge.contrib import ContribError

MAX_PAYLOAD_BYTES = MAX_RECEIPT_BYTES
MAX_ENVELOPE_BYTES = 16 * 1024 * 1024
MAX_KEY_BYTES = 16 * 1024
MAX_TRUSTED_KEYS = 16
CAP_KEYS = ("num_predict", "max_tokens", "max_new_tokens")
METRICS = ("completed_token_rate_tps", "decode_tps", "ttft_ms", "request_duration_ms")
MEASUREMENT_FIELDS = {
    "model",
    "backend",
    "quant",
    "workload",
    "runs",
    "context_length",
    "individual_runs",
    "aggregate",
}
EXECUTION_FIELDS = {
    "requested_count",
    "successful_count",
    "failed_count",
    "elapsed_seconds",
    "elapsed_seconds_basis",
}
REQUEST_FIELDS = {
    "prompt_sha256",
    "prompt_characters",
    "options_sha256",
    "workload",
    "concurrency",
    "arrival_rate",
    "requested_count",
    "context_length",
    "output_token_cap",
    "cap_option",
    "options_scope",
    "arrival_scope",
}
OPTIONS_SCOPE = (
    "exact recorded adapter-map commitment; applied wire defaults/ignored keys unverified"
)
ARRIVAL_SCOPE = "current configured profile only; original Poisson schedule/seed not recorded"
LIMITS = {
    "measurement_truth": "unverified",
    "original_hardware": "unverified",
    "served_weights": "unverified",
    "original_wire_options": "unverified",
    "original_schedule_seed": "unverified",
    "independent_execution": "unverified",
}


def fail(message: str = "malformed bounded signed contribution") -> NoReturn:
    raise ContribError(message) from None


def json_bytes(value: object) -> bytes:
    """Strict encoding never passes through legacy NaN-to-null normalization."""
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    except (ValueError, TypeError, UnicodeError, RecursionError):
        fail()


def hash_json(value: object) -> str:
    return hashlib.sha256(json_bytes(value)).hexdigest()


def parse_json(raw: bytes) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result = {}
        for key, value in items:
            if key in result:
                fail()
            result[key] = value
        return result

    def floating(text: str) -> float:
        value = float(text)
        if not finite(value):
            fail()
        return value

    try:
        result = json.loads(
            raw, object_pairs_hook=pairs, parse_float=floating, parse_constant=lambda _: fail()
        )
        if type(result) is not dict:
            fail()
        return cast(dict[str, Any], result)
    except (ValueError, UnicodeError, TypeError, RecursionError):
        fail()


def held_json(
    source: dict[str, Any] | str | Path, limit: int
) -> tuple[dict[str, Any], bytes, tuple[Path, ...]]:
    from chimeraforge.plan_bundle import _read

    paths: tuple[Path, ...] = ()
    try:
        if isinstance(source, (str, Path)):
            path = Path(source).absolute()
            raw = _read(path, limit)
            paths = (path,)
        elif type(source) is dict:
            raw = json_bytes(source)
        else:
            fail()
        if not 0 < len(raw) <= limit:
            fail()
        return parse_json(raw), raw, paths
    except (ValueError, OSError, TypeError, RecursionError):
        fail()


def public_text(value: object) -> bool:
    return (
        type(value) is str
        and 0 < len(value) <= 512
        and "://" not in value
        and not Path(value).is_absolute()
        and not PurePosixPath(value).is_absolute()
        and not PureWindowsPath(value).is_absolute()
        and ".." not in value.replace("\\", "/").split("/")
    )


def controls(observation: dict[str, Any]) -> dict[str, Any]:
    result = {}
    for name in sorted(FACTS):
        value = _fact(observation, name)
        if type(value) is str and not public_text(value):
            value = None
        result[name] = value
    return result


def observation(flat: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, value in flat.items():
        if "." in name:
            if value is None:
                continue
            root, key = name.split(".")
            result.setdefault(root, {})[key] = value
        else:
            result[name] = value
    return result


def public_native(view: dict[str, Any]) -> dict[str, Any]:
    """The original view is already held/validated; recompute recognized native rates."""
    for name in METRICS:
        _metric(view, name)
    measurement, execution = view["measurement"], view["execution"]
    request = execution["request"]
    caps = [key for key in CAP_KEYS if key in request["options"]]
    if len(caps) != 1:
        fail("recorded request needs one explicit output cap")
    cap = request["options"][caps[0]]
    if type(cap) is not int or not 1 <= cap <= MAX_TOKEN_COUNT:
        fail("recorded output cap must be a positive bounded integer")
    payload = {
        "measurement": {key: measurement[key] for key in MEASUREMENT_FIELDS},
        "execution": {key: execution.get(key) for key in EXECUTION_FIELDS},
        "request": {
            "prompt_sha256": request["prompt_sha256"],
            "prompt_characters": request.get("prompt_characters"),
            "options_sha256": hash_json(request["options"]),
            "workload": request["workload"],
            "concurrency": request["concurrency"],
            "arrival_rate": request.get("arrival_rate"),
            "requested_count": request["requested_count"],
            "context_length": measurement.get("context_length"),
            "output_token_cap": cap,
            "cap_option": caps[0],
            "options_scope": OPTIONS_SCOPE,
            "arrival_scope": ARRIVAL_SCOPE,
        },
        "observed_controls": {
            phase: controls(execution["serving_" + phase]) for phase in ("before", "after")
        },
    }
    return payload


def project(view: dict[str, Any]) -> dict[str, Any]:
    if view["legacy"] or view["execution"] is None or not sha(view["fingerprint"]):
        fail("signing requires a current validated PlanBenchmark envelope")
    payload = {
        "schema_version": 2,
        "kind": "chimeraforge.signed-native-payload",
        "source": {
            "sha256": view["sha256"],
            "fingerprint": view["fingerprint"],
            "scope": "held_file" if view["path"] is not None else "held_snapshot",
        },
        **public_native(view),
        "assurance": dict(LIMITS),
    }
    validate_payload(payload)
    return payload


def validate_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Validate closed public facts without inventing the committed private options."""
    if (
        set(data)
        != {
            "schema_version",
            "kind",
            "source",
            "measurement",
            "execution",
            "request",
            "observed_controls",
            "assurance",
        }
        or type(data["schema_version"]) is not int
        or data["schema_version"] != 2
        or data["kind"] != "chimeraforge.signed-native-payload"
        or data["assurance"] != LIMITS
    ):
        fail()
    source, measurement, execution, request = [
        data[k] for k in ("source", "measurement", "execution", "request")
    ]
    if (
        type(source) is not dict
        or set(source) != {"sha256", "fingerprint", "scope"}
        or not sha(source["sha256"])
        or not sha(source["fingerprint"])
        or source["scope"] not in ("held_file", "held_snapshot")
        or type(measurement) is not dict
        or set(measurement) != MEASUREMENT_FIELDS
        or type(execution) is not dict
        or set(execution) != EXECUTION_FIELDS
        or type(request) is not dict
        or set(request) != REQUEST_FIELDS
    ):
        fail()
    if (
        any(not public_text(measurement[k]) for k in ("model", "backend"))
        or measurement["quant"] is not None
        and not public_text(measurement["quant"])
        or any(
            type(request[k]) is not int or not 1 <= request[k] <= MAX_TOKEN_COUNT
            for k in ("prompt_characters", "context_length", "output_token_cap")
        )
        or type(measurement["context_length"]) is not int
        or measurement["context_length"] != request["context_length"]
        or not sha(request["prompt_sha256"])
        or not sha(request["options_sha256"])
        or request["workload"] not in ("single", "batch", "server")
        or request["workload"] != measurement["workload"]
        or not count(request["requested_count"], minimum=1)
        or request["requested_count"] != measurement["runs"]
        or type(request["concurrency"]) is not int
        or not 1 <= request["concurrency"] <= MAX_SAMPLES
        or request["workload"] == "single"
        and request["concurrency"] != 1
        or request["cap_option"] not in CAP_KEYS
        or request["options_scope"] != OPTIONS_SCOPE
        or request["arrival_scope"] != ARRIVAL_SCOPE
    ):
        fail()
    arrival = request["arrival_rate"]
    if (
        (request["workload"] == "server" and (not finite(arrival) or arrival <= 0))
        or request["workload"] != "server"
        and arrival is not None
        or any(
            not count(execution[k]) for k in ("requested_count", "successful_count", "failed_count")
        )
        or execution["requested_count"] != request["requested_count"]
        or execution["successful_count"] + execution["failed_count"] != execution["requested_count"]
        or not finite(execution["elapsed_seconds"], minimum=0)
        or execution["elapsed_seconds_basis"] != WALL_BASIS
    ):
        fail()
    observed = data["observed_controls"]
    if type(observed) is not dict or set(observed) != {"before", "after"}:
        fail()
    for phase in observed:
        flat = observed[phase]
        if (
            type(flat) is not dict
            or set(flat) != FACTS
            or hash_json(controls(observation(flat))) != hash_json(flat)
        ):
            fail()
    from chimeraforge.bench.gate_inputs import samples

    rows = samples(measurement)
    if len(rows) != execution["successful_count"] or any(
        row.ttft_basis not in ("unknown", "server-prefill-duration", "client-stream-first-content")
        for row in rows
    ):
        fail()
    if any(row.tokens_generated > request["output_token_cap"] for row in rows):
        fail("generated count exceeds explicit signed output cap")
    view: dict[str, Any] = {
        "measurement": measurement,
        "execution": {
            **execution,
            **{"serving_" + phase: observation(observed[phase]) for phase in observed},
        },
        "samples": rows,
        "legacy": False,
    }
    validate_native_aliases(
        rows, view["execution"]["serving_before"], view["execution"]["serving_after"]
    )
    for name in METRICS:
        _metric(view, name)
    return view


def load_benchmark(source: object) -> dict[str, Any]:
    try:
        return cast(dict[str, Any], load_receipt(source))
    except (ValueError, TypeError, KeyError, RecursionError, OSError):
        fail("invalid bounded native benchmark receipt")


def current_view(measurement: dict[str, Any], execution: dict[str, Any]) -> dict[str, Any]:
    """Use the same native validator as held benchmark receipts on the actual runner views."""
    execution = {**execution, "individual_runs": measurement["individual_runs"]}
    rows = validate_population(measurement, execution)
    view = {"measurement": measurement, "execution": execution, "samples": rows, "legacy": False}
    for name in METRICS:
        _metric(view, name)
    return view
