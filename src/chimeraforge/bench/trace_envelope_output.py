"""Closed JUnit cases for one finalized ordinary or whole-fleet assessment."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import NoReturn
from xml.etree import ElementTree as ET

from chimeraforge.bench.fleet_gate_output import MAX_JUNIT_BYTES, _write
from chimeraforge.bench.gate import FACTS, RegressionGate, _cache, _condition_states
from chimeraforge.bench.gate_inputs import finite, sha
from chimeraforge.bench.serving_binding import observed_model
from chimeraforge.bench.trace import _qualify
from chimeraforge.bench.trace_campaign import MAX_REPLICATES
from chimeraforge.bench.trace_envelope import _comparison_view
from chimeraforge.bench.trace_envelope_inputs import MAX_CELLS
from chimeraforge.bench.trace_gate import TraceGatePolicy, _workload
from chimeraforge.bench.trace_gate_inputs import TARGETS
from chimeraforge.fleet_monitor_types import MAX_ENDPOINTS
from chimeraforge.planner.replay import digest

LOG = logging.getLogger(__name__)
KINDS = {
    "chimeraforge.trace-envelope-assessment": "ordinary",
    "chimeraforge.fleet-trace-envelope-assessment": "fleet",
}
OUTCOMES = {"conditional_pass": 0, "observed_breach": 1, "inconclusive": 3}


def fail(message: str) -> NoReturn:
    from chimeraforge.api import PlanError

    raise PlanError("invalid trace envelope output: " + message)


def _strings(value: object) -> list[str]:
    if type(value) is not list or any(type(item) is not str for item in value):
        fail("invalid envelope blocker population")
    return value


def _count(value: object, maximum: int) -> int:
    if type(value) is not int or not 1 <= value <= maximum:
        fail("invalid envelope declared population")
    return value


def _indexed(value: object, count: int) -> list[dict]:
    if type(value) is not list or len(value) != count:
        fail("envelope output must retain the whole declared population")
    for index, item in enumerate(value):
        if type(item) is not dict or type(item.get("index")) is not int or item["index"] != index:
            fail("invalid envelope ordinal population")
    return value


def _ordinary_execution(slot: dict, data: dict) -> tuple[bool, bool]:
    """Use the same native SLO, workload, cache and observed-control primitives."""
    native = slot["receipt"]
    if native is None:
        return True, False
    if type(native) is not dict or not sha(slot.get("evidence_sha256")):
        fail("invalid envelope native execution")
    cases, policy = data["cases"], data["policy"]
    rows = native["requests"]
    if type(rows) is not list or len(rows) != len(cases["ordered_descriptors"]):
        fail("invalid envelope native request population")
    fixed = dict(policy["fixed_controls"])
    if "model" in fixed:
        fixed["model"] = observed_model(fixed["model"], cases["model"])
    view = _comparison_view({"data": native}, cases["model"])
    _, conditions, _ = _condition_states(view, view, TraceGatePolicy(fixed_controls=fixed))
    _, workload = _workload({"data": native})
    cache = _cache(view)
    states = [_qualify(row, policy["targets"]) for row in rows]
    error = bool(
        slot["state"] != "completed"
        or native["clock"]["origin"] is None
        or conditions
        or workload
        or cache["state"] == "mismatch"
        or policy["require_cache_evidence"]
        and cache["state"] == "unknown"
        or any(row["state"] != "completed" for row in rows)
        or any("unknown" in state.values() for state in states)
    )
    return error, any("breach" in state.values() for state in states)


def _fleet_execution(slot: dict, cell: dict, data: dict) -> tuple[bool, bool]:
    population = data["population"]
    members = _indexed(slot["members"], population["original_replicas"])
    rows = _indexed(slot["rows"], cell["requests_per_execution"])
    if type(slot["native_present"]) is not bool:
        fail("invalid envelope native presence")
    if slot["native_present"] and (
        not sha(slot["evidence_sha256"])
        or not sha(slot["embedded_sha256"])
        or type(slot["native_exit_code"]) is not int
        or slot["native_exit_code"] not in (0, 1, 2, 3)
    ):
        fail("invalid envelope native execution identity")
    blocked = not slot["native_present"] or slot["state"] != "completed"
    blocked = blocked or slot["native_exit_code"] != 0
    assigned: list[int] = []
    for member in members:
        indices = member["row_indices"]
        if type(indices) is not list or any(
            type(index) is not int or not 0 <= index < len(rows) for index in indices
        ):
            fail("invalid envelope member request allocation")
        assigned.extend(indices)
        if type(member["conditions"]) is not dict:
            fail("invalid envelope member conditions")
        if slot["native_present"] and set(member["conditions"]) != FACTS:
            fail("envelope must retain every native member condition")
        for condition in member["conditions"].values():
            if (
                type(condition) is not dict
                or condition.get("state") not in ("matched", "mismatch", "unavailable")
                or type(condition.get("required")) is not bool
            ):
                fail("invalid envelope member condition")
            blocked = (
                blocked
                or condition["state"] == "mismatch"
                or (condition["required"] and condition["state"] == "unavailable")
            )
        if member["cache_state"] not in ("known", "unknown", "mismatch"):
            fail("invalid envelope member cache evidence")
        member_blockers = _strings(member["blockers"])
        blocked = bool(
            blocked
            or member_blockers
            or member["cache_state"] == "mismatch"
            or data["policy"]["require_cache_evidence"]
            and member["cache_state"] == "unknown"
        )
        if any(rows[index]["member_index"] != member["index"] for index in indices):
            fail("envelope member request allocation disagrees")
    if sorted(assigned) != list(range(len(rows))):
        fail("envelope must retain every original request once")
    breach = False
    for row in rows:
        if row["outcome"] not in ("pass", "breach", "unknown", "not_completed", "not_requested"):
            fail("invalid envelope request outcome")
        if type(row["timing"]) is not dict or set(row["timing"]) != set(data["policy"]["targets"]):
            fail("invalid envelope request targets")
        for value in row["timing"].values():
            if value is not None and not finite(value, minimum=0):
                fail("invalid envelope timing arithmetic")
        breach = breach or row["outcome"] == "breach"
        blocked = blocked or row["state"] != "completed" or row["outcome"] not in ("pass", "breach")
        blocked = blocked or any(
            threshold is not None and row["timing"][target] is None
            for target, threshold in data["policy"]["targets"].items()
        )
    # Cleanup/clock/workload compatibility is not attributed to individual executions.
    return bool(blocked or cell["blockers"]), breach


def materialize(result: RegressionGate, *, include_junit: bool = True) -> tuple[bytes, bytes]:
    if type(result) is not RegressionGate:
        fail("envelope output requires a finalized assessment")
    data = result.to_dict()
    if (
        data.get("kind") not in KINDS
        or type(data.get("schema_version")) is not int
        or data["schema_version"] != 1
        or not sha(data.get("fingerprint"))
        or data["fingerprint"] != digest({k: v for k, v in data.items() if k != "fingerprint"})
        or data.get("outcome") not in OUTCOMES
        or type(data.get("exit_code")) is not int
        or data["exit_code"] != OUTCOMES[data["outcome"]]
        or bool(_strings(data.get("blockers"))) != (data["exit_code"] == 3)
    ):
        fail("invalid finalized envelope assessment")
    fleet = KINDS[data["kind"]] == "fleet"
    policy = data["policy"]
    targets = policy["targets"]
    if (
        type(targets) is not dict
        or set(targets) != set(TARGETS)
        or not any(value is not None for value in targets.values())
        or any(value is not None and not finite(value, minimum=0) for value in targets.values())
        or type(policy["require_cache_evidence"]) is not bool
    ):
        fail("invalid finalized envelope policy")
    cells = data["cells"]
    if type(cells) is not list or not 1 <= len(cells) <= MAX_CELLS:
        fail("invalid envelope cell population")
    population = data["population"] if fleet else data["cases"]
    executions = _count(
        population["expected_executions" if fleet else "expected_replicates"], MAX_REPLICATES
    )
    if fleet:
        _count(population["original_replicas"], MAX_ENDPOINTS)
        _indexed(cells, len(cells))
    elif len(cells) != len(population["cells"]) or not population["ordered_descriptors"]:
        fail("envelope cell population disagrees with declaration")
    local_markers: set[str] = set()
    for index, cell in enumerate(cells):
        if type(cell) is not dict:
            fail("invalid envelope cell")
        reasons = _strings(cell["blockers"])
        if not fleet and cell["name"] != population["cells"][index]["name"]:
            fail("envelope cell ordering disagrees with declaration")
        prefix = f"cell-{index}:" if fleet else "cell:" + cell["name"] + ":"
        local_markers.update(prefix + reason for reason in reasons)
    if not local_markers <= set(data["blockers"]):
        fail("envelope cell blockers disagree with finalized blockers")
    global_error = bool(set(data["blockers"]) - local_markers)
    breaches = data["known_breaches"]
    if (
        type(breaches) is not list
        or (data["exit_code"] == 0 and breaches)
        or (data["exit_code"] == 1 and not breaches)
    ):
        fail("invalid envelope breach population")
    failed: set[tuple[int, int]] = set()
    for breach in breaches:
        if type(breach) is not dict:
            fail("invalid envelope breach")
        cell_index = (
            breach["cell_index"]
            if fleet
            else next(i for i, cell in enumerate(cells) if cell["name"] == breach["cell"])
        )
        execution_index = breach["execution_index" if fleet else "replica_index"]
        if (
            type(cell_index) is not int
            or not 0 <= cell_index < len(cells)
            or type(execution_index) is not int
            or not 0 <= execution_index < executions
            or breach["target"] not in targets
            or targets[breach["target"]] is None
            or not finite(breach["observed"], minimum=0)
            or not finite(breach["threshold"], minimum=0)
            or breach["threshold"] != targets[breach["target"]]
            or breach["observed"] <= breach["threshold"]
        ):
            fail("invalid envelope breach arithmetic")
        cell = cells[cell_index]
        slot = cell["executions" if fleet else "replicas"][execution_index]
        if fleet:
            row_index = breach["row_index"]
            if type(row_index) is not int or not 0 <= row_index < len(slot["rows"]):
                fail("invalid envelope breached request ordinal")
            row = slot["rows"][row_index]
        else:
            row = next(
                row
                for row in slot["receipt"]["requests"]
                if row["descriptor"]["request_id"] == breach["request_id"]
            )
        if row["timing"][breach["target"]] != breach["observed"]:
            fail("envelope breach disagrees with native request evidence")
        failed.add((cell_index, execution_index))
    suite = (
        ET.Element(
            "testsuite",
            name="chimeraforge.trace-envelope",
            tests=str(1 + len(cells) * (1 + executions)),
            failures="0",
            errors="0",
            skipped="0",
        )
        if include_junit
        else None
    )
    errors, failures = 0, 0

    def case(name: str, error: bool, breach: bool, properties: dict) -> None:
        nonlocal errors, failures
        if suite is None:
            return
        node = ET.SubElement(suite, "testcase", name=name, classname="trace-envelope")
        props = ET.SubElement(node, "properties")
        for key, value in properties.items():
            ET.SubElement(props, "property", name=key, value=str(value))
        if error:
            ET.SubElement(
                node,
                "error",
                type="inconclusive",
                message="Required envelope evidence is incomplete or incompatible",
            )
            errors += 1
        if breach:
            ET.SubElement(
                node, "failure", type="slo-breach", message="Declared native SLO limit exceeded"
            )
            failures += 1

    case(
        "overall",
        data["exit_code"] == 3,
        bool(breaches),
        {
            "kind": KINDS[data["kind"]],
            "fingerprint": data["fingerprint"],
            "exit_code": data["exit_code"],
        },
    )
    for index, cell in enumerate(cells):
        for name in ("arrival_interval_seconds", "nominal_rate_rps"):
            if not finite(cell[name], minimum=0) or cell[name] <= 0:
                fail("invalid envelope cell arithmetic")
        slots = _indexed(cell["executions" if fleet else "replicas"], executions)
        if fleet and (
            cell["original_replicas"] != population["original_replicas"]
            or cell["expected_executions"] != executions
            or type(cell["requests_per_execution"]) is not int
            or cell["requests_per_execution"] < 1
            or cell["total_requests"] != cell["requests_per_execution"] * executions
        ):
            fail("invalid whole-fleet cell population")
        case(
            f"cell-{index}",
            global_error or bool(cell["blockers"]),
            any(i == index for i, _ in failed),
            {name: cell[name] for name in ("arrival_interval_seconds", "nominal_rate_rps")},
        )
        for execution_index, slot in enumerate(slots):
            error, native_breach = (
                _fleet_execution(slot, cell, data) if fleet else _ordinary_execution(slot, data)
            )
            if (native_breach and (index, execution_index) not in failed) or (
                not fleet and native_breach != ((index, execution_index) in failed)
            ):
                fail("envelope known breaches disagree with native execution evidence")
            properties: dict[str, int | str] = {"execution_index": execution_index}
            if slot.get("evidence_sha256") is not None:
                if not sha(slot["evidence_sha256"]):
                    fail("invalid envelope execution evidence identity")
                properties["evidence_sha256"] = slot["evidence_sha256"]
            case(
                f"cell-{index}.execution-{execution_index}",
                global_error or error,
                (index, execution_index) in failed,
                properties,
            )
    xml = b""
    if suite is not None:
        suite.set("errors", str(errors))
        suite.set("failures", str(failures))
        xml = ET.tostring(suite, encoding="utf-8", xml_declaration=True) + b"\n"
        if len(xml) > MAX_JUNIT_BYTES:
            fail("complete envelope JUnit exceeds its byte profile")
    raw = (json.dumps(data, indent=2, allow_nan=False) + "\n").encode("utf-8")
    return raw, xml


def write_trace_envelope(
    result: RegressionGate, *, out: str | Path | None = None, junit: str | Path | None = None
) -> None:
    """Admit requested buffers before separately atomic writes; not a transaction."""
    from chimeraforge.api import PlanError
    from chimeraforge.plan_study import protect_output

    if out is None and junit is None:
        fail("envelope output requires a destination")
    try:
        raw, xml = materialize(result, include_junit=junit is not None)
        outputs = [Path(value) for value in (out, junit) if value is not None]
        for index, path in enumerate(outputs):
            protect_output(
                path, (*result._protected_paths, *outputs[:index], *outputs[index + 1 :])
            )
        for destination, payload in ((out, raw), (junit, xml)):
            if destination is not None:
                _write(Path(destination), payload)
    except (
        PlanError,
        OSError,
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        StopIteration,
        AttributeError,
        OverflowError,
        RecursionError,
    ) as exc:
        LOG.info("trace envelope output refused (%s)", type(exc).__name__)
        raise PlanError("cannot publish complete trace envelope assessment") from None
