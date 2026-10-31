"""Strict held receiving of complete or partial original-fleet observations."""

from __future__ import annotations

from datetime import datetime
import json
import logging
from pathlib import Path
import re
from typing import Any, NoReturn

from chimeraforge.bench import serving
from chimeraforge.bench.gate_inputs import finite
from chimeraforge.fleet_monitor_json import (
    encode_public,
    MAX_FLEET_JSON_BYTES,
    PUBLIC_FIELDS,
    public_projection,
)
from chimeraforge.fleet_monitor_types import (
    FleetEndpoint,
    FleetMonitorError,
    FleetMonitorReport,
    FleetMonitorRequest,
    FleetSlot,
    MAX_BODY_BYTES,
    MAX_CLEANUP_SECONDS,
    MAX_ENDPOINTS,
    MAX_MODEL_CHARS,
    MAX_REQUESTS,
    MAX_TOTAL_WINDOWS,
)
from chimeraforge.monitor import (
    MetricAssessment,
    MonitorRequest,
    MonitorWindow,
    _classify_bounds,
    _outcome,
    evaluate_window,
)
from chimeraforge.monitor_binding import assemble_binding
from chimeraforge.plan_check import identity

LOG = logging.getLogger(__name__)
CONTROL_FIELDS = {
    "schema_version",
    "endpoints",
    "interval",
    "windows",
    "timeout",
    "observation_seconds",
    "cleanup_seconds",
    "concurrency",
    "max_requests",
    "max_body_bytes",
    "targets",
    "target_sources",
}
ROOT_FIELDS = {
    "schema_version",
    "backend",
    "model",
    "slots",
    "plan",
    "target_sources",
    "budget",
    "cleanup",
    "cancelled",
    "monitor_tool_version",
    "declared_coverage",
    "exit_code",
    "outcome",
    "limits",
}
SOURCES = {"explicit_override", "saved_request", "not_set"}
MAX_PRODUCER_VERSION_CHARS = 128


def fail(message: str) -> NoReturn:
    from chimeraforge.api import PlanError

    raise PlanError("invalid fleet monitor input: " + message) from None


def same(actual: Any, expected: Any, *, exact_types: bool = False) -> bool:
    """Strict booleans/counts/containers; native real values permit int/float spelling."""
    if type(expected) in PUBLIC_FIELDS:
        expected = public_projection(expected)
    if type(expected) is dict:
        return (
            type(actual) is dict
            and set(actual) == set(expected)
            and all(
                same(actual[key], value, exact_types=exact_types) for key, value in expected.items()
            )
        )
    if type(expected) in (list, tuple):
        return (
            (type(actual) is type(expected) if exact_types else type(actual) in (list, tuple))
            and len(actual) == len(expected)
            and all(
                same(left, right, exact_types=exact_types) for left, right in zip(actual, expected)
            )
        )
    if type(expected) is float and not exact_types:
        return finite(actual) and actual == expected
    return type(actual) is type(expected) and actual == expected


def held_json(source: object) -> tuple[dict, bytes, tuple[Path, ...]]:
    from chimeraforge.api import _unique_object
    from chimeraforge.plan_bundle import _read

    protected: tuple[Path, ...] = ()
    if type(source) is FleetMonitorReport:
        raw = source._held_bytes if source._held_bytes is not None else source.json_bytes()
        protected = source._input_paths
    elif isinstance(source, (str, Path)):
        path = Path(source).absolute()
        raw = _read(path, MAX_FLEET_JSON_BYTES)
        protected = (path,)
    elif type(source) is dict:
        raw = encode_public(source)
    else:
        fail("expected a complete report object or JSON file")
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_FLEET_JSON_BYTES:
        fail("JSON exceeds 8 MiB receiving limit")

    def number(text: str) -> float:
        value = float(text)
        if not finite(value):
            fail("nonfinite number")
        return value

    data = json.loads(
        raw,
        object_pairs_hook=_unique_object,
        parse_float=number,
        parse_constant=lambda _: fail("nonfinite number"),
    )
    if type(data) is not dict:
        fail("root must be an object")
    if type(source) is FleetMonitorReport and source._held_bytes is not None:
        if (
            type(source.slots) is not tuple
            or type(data.get("slots")) is not list
            or len(source.slots) != len(data["slots"])
        ):
            fail("loaded typed report changed after its held-byte snapshot")
        current = public_projection(source)
        current["slots"] = list(source.slots)
        if not same(data, current, exact_types=True):
            fail("loaded typed report changed after its held-byte snapshot")
    return data, raw, protected


def held_source(saved: Any) -> tuple[dict, tuple[Path, ...]]:
    from chimeraforge.deployment_verify import _source

    paths = (Path(saved).absolute(),) if isinstance(saved, (str, Path)) else ()
    try:
        artifact, _, _ = _source(saved)
    except (OSError, ValueError, TypeError, KeyError, RecursionError) as exc:
        LOG.info("fleet source receiving refused (%s)", type(exc).__name__)
        fail("original saved plan is malformed or unavailable")
    return artifact.to_dict(), paths


def select_plan(
    held: tuple[dict, tuple[Path, ...]], index: int
) -> tuple[dict, dict, tuple[Path, ...]]:
    if type(index) is not int or index < 0:
        fail("candidate index must be a non-negative integer")
    data, paths = held
    candidate = data["result"]["candidates"][index]
    if (
        candidate["backend"] not in ("vllm", "sglang")
        or type(candidate["n_agents"]) is not int
        or not 1 <= candidate["n_agents"] <= MAX_ENDPOINTS
        or type(candidate["model"]) is not str
        or not 0 < len(candidate["model"]) <= MAX_MODEL_CHARS
    ):
        fail("original candidate is not a supported passive fleet")
    return data, candidate, paths


def held_plan(saved: Any, index: int) -> tuple[dict, dict, tuple[Path, ...]]:
    return select_plan(held_source(saved), index)


def controls_from(value: dict, source: dict, candidate: dict) -> FleetMonitorRequest:
    from chimeraforge.fleet_monitor import _admit, _targets

    if type(value) is not dict or set(value) != CONTROL_FIELDS:
        fail("effective controls need a complete closed snapshot")
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        fail("unsupported effective controls version")
    if (
        type(value["endpoints"]) is not list
        or len(value["endpoints"]) != candidate["n_agents"]
        or any(type(row) is not dict or set(row) != {"id", "url"} for row in value["endpoints"])
        or type(value["targets"]) is not dict
        or set(value["targets"]) != {"ttft_ms", "tpot_ms"}
        or type(value["target_sources"]) is not dict
        or set(value["target_sources"]) != {"ttft", "tpot"}
        or any(type(v) is not str or v not in SOURCES for v in value["target_sources"].values())
    ):
        fail("invalid effective endpoint/target controls")
    request = FleetMonitorRequest(
        tuple(FleetEndpoint(row["id"], row["url"]) for row in value["endpoints"]),
        **{
            name: value[name]
            for name in (
                "interval",
                "windows",
                "timeout",
                "observation_seconds",
                "cleanup_seconds",
                "concurrency",
                "max_requests",
                "max_body_bytes",
            )
        },
        ttft_slo=value["targets"]["ttft_ms"]
        if value["target_sources"]["ttft"] == "explicit_override"
        else None,
        tpot_slo=value["targets"]["tpot_ms"]
        if value["target_sources"]["tpot"] == "explicit_override"
        else None,
    )
    endpoints = _admit(request, candidate["n_agents"])
    if not same(value["endpoints"], [{"id": e.id, "url": e.url} for e in endpoints]):
        fail("endpoint controls are not canonical")
    targets, sources = _targets(source, request)
    if not same(value["target_sources"], sources) or not same(
        value["targets"], {"ttft_ms": targets["ttft_slo"], "tpot_ms": targets["tpot_slo"]}
    ):
        fail("resolved target/source controls disagree with the original plan")
    for endpoint in endpoints:
        MonitorRequest(candidate["backend"], endpoint.url, candidate["model"], **targets).validate()
    return request


def _assessment(value: dict, template: MetricAssessment) -> MetricAssessment:
    if type(value) is not dict or set(value) != set(PUBLIC_FIELDS[MetricAssessment]):
        fail("metric assessment needs exact native fields")
    for key in ("metric", "semantics", "target_ms", "unit", "percentile"):
        if not same(value[key], getattr(template, key)):
            fail("metric contract or target changed")
    if type(value["reason"]) is not str:
        fail("metric reason must be text")
    samples, lower, upper = (value[key] for key in ("samples", "p95_lower_ms", "p95_upper_ms"))
    if samples is None:
        if lower is not None or upper is not None or value["confidence"] != "unknown":
            fail("unavailable metric has contradictory bounds")
        if value["outcome"] != "unknown" or not value["reason"]:
            fail("unavailable metric must remain unknown")
    else:
        if (
            type(samples) is not int
            or samples <= 0
            or not finite(samples)
            or not finite(lower, minimum=0)
            or upper is not None
            and (not finite(upper, minimum=0) or upper < lower)
            or template.metric is None
            or value["confidence"] != "histogram-bound"
        ):
            fail("invalid histogram-bound evidence")
        outcome, reason = _classify_bounds(lower, upper, template.target_ms)
        if value["outcome"] != outcome or value["reason"] != reason:
            fail("native bucket assessment was relabeled")
    return MetricAssessment(**value)


def _window(value: dict, backend: str, model: str, targets: dict) -> MonitorWindow:
    if type(value) is not dict or set(value) != set(PUBLIC_FIELDS[MonitorWindow]):
        fail("window needs exact native fields")
    if value["backend"] != backend or value["model"] != model or not finite(value["seconds"]):
        fail("window identity or duration is invalid")
    if value["seconds"] <= 0 or type(value["observed_at"]) is not str:
        fail("window duration/time is invalid")
    stamp = datetime.fromisoformat(value["observed_at"])
    if stamp.tzinfo is None:
        fail("window timestamp must be timezone aware")
    template = evaluate_window("", "", backend=backend, model=model, seconds=1, **targets)
    if type(value["metrics"]) is not dict or set(value["metrics"]) != set(template.metrics):
        fail("window needs all native metrics")
    metrics = {
        name: _assessment(value["metrics"][name], row) for name, row in template.metrics.items()
    }
    outcome = _outcome([row.outcome for row in metrics.values() if row.target_ms is not None])
    if value["outcome"] != outcome:
        fail("window aggregate changed")
    return MonitorWindow(backend, model, value["seconds"], value["observed_at"], outcome, metrics)


def _slot(
    value: dict,
    source: dict,
    candidate: dict,
    index: int,
    sources: dict,
    controls: dict | None,
    producer: str,
) -> FleetSlot:
    from chimeraforge.fleet_monitor import _endpoint

    if type(value) is not dict or set(value) != set(PUBLIC_FIELDS[FleetSlot]):
        fail("slot needs exact native fields")
    endpoint = _endpoint(FleetEndpoint(value["id"], value["url"]))
    if endpoint.url != value["url"]:
        fail("slot URL is not canonical")
    if (
        value["state"] not in ("unstarted", "cancelled", "error", "complete")
        or value["error"] is not None
        and (type(value["error"]) is not str)
        or value["state"] == "complete"
        and value["error"] is not None
        or type(value["windows"]) is not list
        or len(value["windows"]) > MAX_TOTAL_WINDOWS
        or type(value["observations"]) is not list
    ):
        fail("invalid slot state/population")
    count = len(value["windows"])
    if len(value["observations"]) not in (count, count + 1):
        fail("metadata must retain the native window prefix")
    if value["state"] == "complete" and (not count or len(value["observations"]) != count + 1):
        fail("completed slot lacks full brackets")
    if controls is not None:
        targets = {name + "_slo": controls["targets"][name + "_ms"] for name in ("ttft", "tpot")}
        if (
            count > controls["windows"]
            or value["state"] == "complete"
            and count != controls["windows"]
        ):
            fail("window population disagrees with requested controls")
    else:
        targets = {
            name + "_slo": value["windows"][0]["metrics"][name]["target_ms"] if count else None
            for name in ("ttft", "tpot")
        }
        for name in ("ttft", "tpot"):
            target = targets[name + "_slo"]
            saved_target = source["inputs"][name + "_slo"]
            if (
                sources[name] == "not_set"
                and (target is not None or saved_target is not None)
                or sources[name] == "saved_request"
                and (saved_target is None or count and not same(target, saved_target))
                or sources[name] == "explicit_override"
                and count
                and target is None
            ):
                fail("legacy target source contradicts saved/native target evidence")
    if value["state"] == "unstarted" and (count or value["observations"]):
        fail("unstarted slot cannot contain observed evidence")
    for snapshot in value["observations"]:
        if type(snapshot) is not dict or not same(snapshot, serving.safe_observation(snapshot)):
            fail("observation is outside the native public projection")
    windows = [
        _window(row, candidate["backend"], candidate["model"], targets) for row in value["windows"]
    ]
    slo = (
        "breach"
        if any(w.outcome == "breach" for w in windows)
        else ("unknown" if not windows or any(w.outcome == "unknown" for w in windows) else "pass")
    )
    if value["slo"] != slo:
        fail("slot SLO aggregate changed")
    effective = MonitorRequest(candidate["backend"], endpoint.url, candidate["model"], **targets)
    binding = assemble_binding(
        source,
        candidate,
        index,
        effective,
        sources,
        value["observations"],
        retain_prefix=True,
        producer_version=producer,
    )
    # Compare against the already held bounded tree without copying or rendering
    # reconstructed repeated references. Compact legacy input need not pretty-fit.
    if not same(value["binding"], binding):
        fail("saved binding disagrees with original plan/retained metadata")
    return FleetSlot(
        endpoint.id,
        endpoint.url,
        value["state"],
        slo,
        value["error"],
        windows,
        value["observations"],
        value["binding"],
    )


def _resources(data: dict, count: int, controls: dict | None) -> None:
    budget, cleanup = data["budget"], data["cleanup"]
    if type(data["cancelled"]) is not bool:
        fail("cancelled must be boolean")
    if type(budget) is not dict or set(budget) != {
        "requests",
        "max_requests",
        "accepted_body_bytes",
        "max_body_bytes",
        "termination",
        "byte_scope",
    }:
        fail("budget needs exact native fields")
    if (
        any(
            type(budget[key]) is not int or budget[key] < 0
            for key in ("requests", "max_requests", "accepted_body_bytes", "max_body_bytes")
        )
        or not 1 <= budget["max_requests"] <= MAX_REQUESTS
        or not 1 <= budget["max_body_bytes"] <= MAX_BODY_BYTES
    ):
        fail("invalid shared budget counts")
    if (
        budget["requests"] > budget["max_requests"]
        or budget["accepted_body_bytes"] > budget["max_body_bytes"]
        or budget["termination"]
        not in (None, "request_limit", "body_limit", "observation_deadline")
        or budget["byte_scope"]
        != "accepted identity-encoded body chunks; not wire/transport buffers"
    ):
        fail("invalid shared budget outcome")
    minimum_contacts = sum(
        len(slot["windows"]) + 1 if slot["windows"] else int(bool(slot["observations"]))
        for slot in data["slots"]
    )
    if budget["requests"] < minimum_contacts:
        fail("observed windows exceed reported native contacts")
    if type(cleanup) is not dict or set(cleanup) != {
        "state",
        "budget_seconds",
        "allowance_exceeded",
        "resources_closed",
        "close_errors",
        "owned_pools",
        "closed_pools",
        "joined_endpoint_tasks",
    }:
        fail("cleanup needs exact native fields")
    if (
        not finite(cleanup["budget_seconds"])
        or not 0 < cleanup["budget_seconds"] <= MAX_CLEANUP_SECONDS
        or any(type(cleanup[key]) is not bool for key in ("allowance_exceeded", "resources_closed"))
        or any(
            type(cleanup[key]) is not int or cleanup[key] < 0
            for key in ("close_errors", "owned_pools", "closed_pools", "joined_endpoint_tasks")
        )
        or cleanup["owned_pools"] != 2 * count
        or cleanup["closed_pools"] > cleanup["owned_pools"]
        or cleanup["joined_endpoint_tasks"] not in (0, count)
        or cleanup["resources_closed"]
        and cleanup["closed_pools"] != cleanup["owned_pools"]
    ):
        fail("invalid native cleanup ownership/counts")
    state = (
        "completed"
        if cleanup["resources_closed"]
        and not cleanup["allowance_exceeded"]
        and not cleanup["close_errors"]
        else "incomplete"
    )
    if cleanup["state"] != state:
        fail("cleanup outcome changed")
    if cleanup["joined_endpoint_tasks"] == 0 and (
        not data["cancelled"]
        or budget["requests"]
        or any(
            slot["state"] != "unstarted" or slot["windows"] or slot["observations"]
            for slot in data["slots"]
        )
    ):
        fail("missing endpoint-task ownership")
    if controls is not None and (
        any(not same(budget[key], controls[key]) for key in ("max_requests", "max_body_bytes"))
        or not same(cleanup["budget_seconds"], controls["cleanup_seconds"])
    ):
        fail("resource controls disagree with requested values")


def from_held(
    held: tuple[dict, bytes, tuple[Path, ...]],
    plan: tuple[dict, dict, tuple[Path, ...]],
    index: int,
) -> FleetMonitorReport:
    data, raw, paths = held
    source, candidate, plan_paths = plan
    version = data.get("schema_version")
    expected_keys = ROOT_FIELDS | ({"effective_controls"} if version == 2 else set())
    if type(version) is not int or version not in (1, 2) or set(data) != expected_keys:
        fail("unsupported closed report schema")
    producer = data["monitor_tool_version"]
    if (
        type(producer) is not str
        or len(producer) > MAX_PRODUCER_VERSION_CHARS
        or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+[A-Za-z0-9.+-]*", producer)
    ):
        fail("invalid declared producer version")
    expected_plan = {
        "fingerprint": source["fingerprint"],
        "candidate_index": index,
        "identity": identity(candidate),
        "tool_version": source["tool"]["version"],
    }
    if (
        data["backend"] != candidate["backend"]
        or data["model"] != candidate["model"]
        or not same(data["plan"], expected_plan)
    ):
        fail("receipt does not bind the supplied original plan/selection")
    controls = data["effective_controls"] if version == 2 else None
    if controls is not None:
        controls_from(controls, source, candidate)
    elif version == 2:
        fail("schema2 requires effective controls")
    sources = data["target_sources"]
    if (
        type(sources) is not dict
        or set(sources) != {"ttft", "tpot"}
        or any(type(value) is not str or value not in SOURCES for value in sources.values())
    ):
        fail("invalid target source labels")
    if controls is not None and not same(sources, controls["target_sources"]):
        fail("target source labels disagree")
    if type(data["slots"]) is not list or len(data["slots"]) != candidate["n_agents"]:
        fail("all original member slots are required")
    slots = tuple(
        _slot(row, source, candidate, index, sources, controls, producer) for row in data["slots"]
    )
    if len({row.id for row in slots}) != len(slots) or len({row.url for row in slots}) != len(
        slots
    ):
        fail("duplicate declared member")
    if sum(len(row.windows) for row in slots) > MAX_TOTAL_WINDOWS:
        fail("observed window population exceeds native bounds")
    if controls is not None and not same(
        controls["endpoints"], [{"id": row.id, "url": row.url} for row in slots]
    ):
        fail("ordered member controls disagree")
    _resources(data, len(slots), controls)
    report = FleetMonitorReport(
        candidate["backend"],
        candidate["model"],
        slots,
        expected_plan,
        sources,
        data["budget"],
        data["cleanup"],
        data["cancelled"],
        producer,
        version,
        controls,
        (*paths, *plan_paths),
        _received_raw=raw,
    )
    if not same(data, public_projection(report)):
        fail("native derived coverage/outcome changed")
    return report


def load_fleet_monitor(
    source: object, saved: Any, *, candidate_index: int = 0
) -> FleetMonitorReport:
    """Consistency against held original plan bytes is not traffic/source authentication."""
    from chimeraforge.api import PlanError

    try:
        return from_held(held_json(source), held_plan(saved, candidate_index), candidate_index)
    except PlanError:
        raise
    except (
        FleetMonitorError,
        OSError,
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        AttributeError,
        RecursionError,
        OverflowError,
    ) as exc:
        LOG.info("fleet monitor receiving refused (%s)", type(exc).__name__)
        fail("malformed, unavailable or over-limit report/plan")
