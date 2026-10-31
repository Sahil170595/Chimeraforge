"""Complete population/metric JUnit and exact admitted JSON per-file publication."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from xml.etree import ElementTree as ET

from chimeraforge.bench.fleet_gate_output import _write
from chimeraforge.fleet_monitor_gate import KIND
from chimeraforge.fleet_monitor_gate_types import FleetMonitorGate
from chimeraforge.fleet_monitor_json import MAX_FLEET_JSON_BYTES
from chimeraforge.fleet_monitor_receipt import fail

LOG = logging.getLogger(__name__)


def _materialize(result: FleetMonitorGate) -> tuple[bytes, bytes]:
    if type(result) is not FleetMonitorGate:
        fail("output requires a finalized fleet monitor decision")
    raw = result.json_bytes()
    data = json.loads(raw)
    if (
        data.get("kind") != KIND
        or type(data.get("exit_code")) is not int
        or data["exit_code"] not in (0, 1, 3)
        or data.get("outcome")
        != {0: "conditional_pass", 1: "breach", 3: "inconclusive"}[data["exit_code"]]
        or type(data.get("cases")) is not list
        or not data["cases"]
    ):
        fail("invalid finalized passive decision")
    suite = ET.Element(
        "testsuite",
        name="chimeraforge.fleet-monitor",
        tests=str(1 + len(data["cases"])),
        skipped="0",
    )
    population = ET.SubElement(suite, "testcase", name="population", classname="fleet-monitor")
    failures, errors = 0, 0
    if data["exit_code"] == 3:
        ET.SubElement(
            population,
            "error",
            type="inconclusive",
            message="Whole-fleet eligibility is incomplete",
        )
        errors += 1
    for row in data["cases"]:
        expected_state = (
            "inconclusive"
            if data["exit_code"] == 3
            else ("supporting" if row["arm"] == "baseline" else row["native_outcome"])
        )
        if row["state"] != expected_state or data["exit_code"] == 0 and row["state"] == "breach":
            fail("metric cases disagree with the finalized passive decision")
        case = ET.SubElement(
            suite,
            "testcase",
            classname="fleet-monitor." + row["arm"],
            name=f"{row['member_id']}/window-{row['window_index']}/{row['metric']}",
        )
        properties = ET.SubElement(case, "properties")
        for key in ("native_outcome", "samples", "p95_lower_ms", "p95_upper_ms", "target_ms"):
            ET.SubElement(properties, "property", name=key, value=str(row[key]))
        ET.SubElement(
            properties,
            "property",
            name="role",
            value="supporting-only" if row["arm"] == "baseline" else "acceptance",
        )
        if row["state"] == "inconclusive":
            ET.SubElement(
                case,
                "error",
                type="inconclusive",
                message="Required whole-fleet evidence is unavailable",
            )
            errors += 1
        elif row["state"] == "breach":
            ET.SubElement(
                case,
                "failure",
                type="slo_breach",
                message="Candidate native bucket bounds breach the declared SLO",
            )
            failures += 1
    if data["exit_code"] == 1 and not failures:
        fail("eligible breach requires a candidate failure case")
    suite.set("failures", str(failures))
    suite.set("errors", str(errors))
    xml = ET.tostring(suite, encoding="utf-8", xml_declaration=True) + b"\n"
    if len(xml) > MAX_FLEET_JSON_BYTES:
        fail("complete passive JUnit exceeds 8 MiB output limit")
    return raw, xml


def publish(
    result: FleetMonitorGate,
    *,
    out: str | Path | None = None,
    junit: str | Path | None = None,
) -> bytes:
    from chimeraforge.api import PlanError
    from chimeraforge.plan_study import protect_output

    try:
        raw, xml = _materialize(result)
        outputs = [Path(value) for value in (out, junit) if value is not None]
        for index, path in enumerate(outputs):
            protect_output(
                path, (*result._protected_paths, *outputs[:index], *outputs[index + 1 :])
            )
        for value, payload in ((out, raw), (junit, xml)):
            if value is not None:
                assert payload is not None
                _write(Path(value), payload)
        return raw
    except PlanError:
        raise
    except (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        OSError,
        OverflowError,
        RecursionError,
    ) as exc:
        LOG.info("passive gate output refused (%s)", type(exc).__name__)
        fail("passive decision output is malformed, unavailable or over-limit")


def write_fleet_monitor_gate(
    result: FleetMonitorGate,
    *,
    out: str | Path | None = None,
    junit: str | Path | None = None,
) -> None:
    """Preflight both sinks before per-file replacement; later errors do not roll back."""
    if out is None and junit is None:
        fail("passive gate output requires a destination")
    publish(result, out=out, junit=junit)
