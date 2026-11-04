"""Bounded JSON/JUnit projections of one finalized fleet gate decision."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from tempfile import NamedTemporaryFile
from xml.etree import ElementTree as ET

from chimeraforge.bench.fleet_trace_gate import KIND
from chimeraforge.bench.gate import RegressionGate
from chimeraforge.bench.gate_inputs import MAX_TOTAL_BYTES, fail, finite
from chimeraforge.bench.trace_gate import RULES
from chimeraforge.planner.replay import digest

MAX_JUNIT_BYTES = 64 * 1024
LOG = logging.getLogger(__name__)
OUTCOMES = {"conditional_pass": 0, "regression": 1, "inconclusive": 3}


def _materialize(result: RegressionGate) -> tuple[bytes, bytes]:
    if type(result) is not RegressionGate:
        fail("fleet gate output requires a finalized fleet decision")
    data = result.to_dict()
    content = {key: value for key, value in data.items() if key != "fingerprint"}
    if (
        data.get("kind") != KIND
        or data.get("fingerprint") != digest(content)
        or data.get("outcome") not in OUTCOMES
        or type(data.get("exit_code")) is not int
        or data["exit_code"] != OUTCOMES[data["outcome"]]
        or type(data.get("metrics")) is not dict
        or not data["metrics"]
        or not set(data["metrics"]) <= RULES.keys()
        or set(data["metrics"]) != set(data.get("policy", {}).get("trace", {}).get("rules", {}))
    ):
        fail("invalid finalized fleet decision")
    suite = ET.Element(
        "testsuite",
        name="chimeraforge.fleet-trace",
        tests=str(1 + len(data["metrics"])),
        failures="0",
        errors="0",
        skipped="0",
    )
    failures, errors = 0, 0
    population = ET.SubElement(suite, "testcase", name="population", classname="fleet-trace")
    if data["exit_code"] == 3:
        ET.SubElement(
            population,
            "error",
            type="inconclusive",
            message="Required fleet evidence is incomplete",
        )
        errors += 1
    for name, metric in data["metrics"].items():
        if type(metric) is not dict or metric.get("state") not in (
            "pass",
            "regression",
            "inconclusive",
        ):
            fail("invalid finalized fleet metric")
        if data["exit_code"] == 3 and metric["state"] != "inconclusive":
            fail("inconclusive fleet metrics cannot pass")
        if data["exit_code"] == 0 and metric["state"] != "pass":
            fail("passing fleet metrics must agree with the finalized decision")
        if data["exit_code"] == 1 and metric["state"] == "inconclusive":
            fail("eligible regression cannot contain inconclusive metrics")
        case = ET.SubElement(suite, "testcase", name=name, classname="fleet-trace")
        properties = ET.SubElement(case, "properties")
        for key in ("baseline", "candidate", "regression_fraction", "max_regression_fraction"):
            value = metric.get(key)
            if value is not None and not finite(value):
                fail("invalid finalized fleet arithmetic")
            ET.SubElement(
                properties,
                "property",
                name=key,
                value="unavailable" if value is None else str(value),
            )
        if data["exit_code"] == 3:
            ET.SubElement(
                case, "error", type="inconclusive", message="Required fleet evidence is incomplete"
            )
            errors += 1
        elif metric["state"] == "regression":
            ET.SubElement(
                case, "failure", type="regression", message="Declared regression limit exceeded"
            )
            failures += 1
    suite.set("failures", str(failures))
    suite.set("errors", str(errors))
    if data["exit_code"] == 1 and not failures:
        fail("finalized regression needs a failed declared metric")
    raw = (json.dumps(data, indent=2, allow_nan=False) + "\n").encode("utf-8")
    xml = ET.tostring(suite, encoding="utf-8", xml_declaration=True) + b"\n"
    if len(raw) > MAX_TOTAL_BYTES or len(xml) > MAX_JUNIT_BYTES:
        fail("fleet gate output exceeds its byte admission limit")
    return raw, xml


def _write(path: Path, raw: bytes) -> None:
    temporary = None
    write_error: OSError | None = None
    cleanup_error: OSError | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(dir=path.parent, suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(raw)
        temporary.replace(path)
    except OSError as exc:
        LOG.info("fleet gate output failed (%s)", type(exc).__name__)
        write_error = exc
    finally:
        try:
            if temporary is not None and temporary.exists():
                temporary.unlink()
        except OSError as exc:
            LOG.info("fleet gate temporary cleanup failed (%s)", type(exc).__name__)
            cleanup_error = exc
    if write_error is not None:
        fail("fleet gate output could not be written")
    if cleanup_error is not None:
        fail("fleet gate temporary cleanup could not be completed")


def write_fleet_trace_gate(
    result: RegressionGate,
    *,
    out: str | Path | None = None,
    junit: str | Path | None = None,
) -> None:
    """Admit both projections before per-file atomic writes; this is not a transaction."""
    from chimeraforge.plan_study import protect_output

    try:
        raw, xml = _materialize(result)
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError, RecursionError) as exc:
        LOG.info("fleet gate projection refused (%s)", type(exc).__name__)
        fail("invalid or over-limit finalized fleet decision")
    outputs = [Path(value) for value in (out, junit) if value is not None]
    if not outputs:
        fail("fleet gate output requires a destination")
    for i, path in enumerate(outputs):
        protect_output(path, (*result._protected_paths, *outputs[:i], *outputs[i + 1 :]))
    for value, payload in ((out, raw), (junit, xml)):
        if value is not None:
            _write(Path(value), payload)
