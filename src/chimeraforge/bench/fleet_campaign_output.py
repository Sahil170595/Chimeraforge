"""Complete finalized campaign JSON/JUnit before protected per-file publication."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from xml.etree import ElementTree as ET

from chimeraforge.bench.fleet_campaign_gate import KIND
from chimeraforge.bench.fleet_campaign_types import (
    FleetTraceCampaignGate,
    FleetTraceCampaignError,
    canonical_hash,
)
from chimeraforge.bench.fleet_gate_output import MAX_JUNIT_BYTES, _write
from chimeraforge.bench.gate_inputs import fail, finite
from chimeraforge.bench.trace_gate import RULES

LOG = logging.getLogger(__name__)
OUTCOMES = {"conditional_pass": 0, "regression": 1, "inconclusive": 3}


def materialize(result: FleetTraceCampaignGate) -> tuple[bytes, bytes]:
    if type(result) is not FleetTraceCampaignGate:
        fail("campaign output requires a finalized campaign decision")
    raw = result.json_bytes()
    data = json.loads(raw)
    if (
        data.get("kind") != KIND
        or data.get("fingerprint")
        != canonical_hash({k: v for k, v in data.items() if k != "fingerprint"})
        or data.get("outcome") not in OUTCOMES
        or type(data.get("exit_code")) is not int
        or data["exit_code"] != OUTCOMES[data["outcome"]]
        or bool(data.get("blockers")) != (data["exit_code"] == 3)
    ):
        fail("invalid finalized campaign decision")
    rules = data["policy"]["fleet"]["trace"]["rules"]
    count = max(
        data["policy"]["expected_executions"],
        *(data["inputs"][arm]["population"]["executions"] for arm in ("baseline", "candidate")),
    )
    if (
        type(rules) is not dict
        or not rules
        or not set(rules) <= RULES.keys()
        or type(data["pairs"]) is not list
        or len(data["pairs"]) != count
    ):
        fail("campaign output is missing declared execution/metric cases")
    suite = ET.Element(
        "testsuite",
        name="chimeraforge.fleet-trace-campaign",
        tests=str(1 + count * (1 + len(rules))),
        failures="0",
        errors="0",
        skipped="0",
    )
    errors, failures = 0, 0

    def population(name: str) -> None:
        nonlocal errors
        case = ET.SubElement(suite, "testcase", name=name, classname="fleet-trace-campaign")
        if data["exit_code"] == 3:
            ET.SubElement(
                case,
                "error",
                type="inconclusive",
                message="Required campaign population evidence is incomplete",
            )
            errors += 1

    population("campaign-population")
    for index, pair in enumerate(data["pairs"]):
        if (
            type(pair) is not dict
            or type(pair["index"]) is not int
            or pair["index"] != index
            or type(pair["metrics"]) is not dict
            or set(pair["metrics"]) != set(rules)
        ):
            fail("campaign execution cases do not match declared policy")
        population(f"execution-{index}.fleet-population")
        for name, metric in pair["metrics"].items():
            state = metric.get("state")
            if (
                state not in {"pass", "regression", "inconclusive"}
                or data["exit_code"] == 3
                and state != "inconclusive"
                or data["exit_code"] == 0
                and state != "pass"
                or data["exit_code"] == 1
                and state == "inconclusive"
            ):
                fail("campaign metric case contradicts finalized eligibility")
            case = ET.SubElement(
                suite,
                "testcase",
                name=f"execution-{index}.{name}",
                classname="fleet-trace-campaign",
            )
            properties = ET.SubElement(case, "properties")
            for key in ("baseline", "candidate", "regression_fraction", "max_regression_fraction"):
                value = metric.get(key)
                if value is not None and not finite(value):
                    fail("invalid finalized campaign arithmetic")
                ET.SubElement(
                    properties,
                    "property",
                    name=key,
                    value="unavailable" if value is None else str(value),
                )
            if data["exit_code"] == 3:
                ET.SubElement(
                    case,
                    "error",
                    type="inconclusive",
                    message="Required campaign evidence is incomplete",
                )
                errors += 1
            elif state == "regression":
                ET.SubElement(
                    case,
                    "failure",
                    type="regression",
                    message="Declared native regression limit exceeded",
                )
                failures += 1
    if data["exit_code"] == 1 and failures == 0:
        fail("regression decision requires a failed metric case")
    suite.set("errors", str(errors))
    suite.set("failures", str(failures))
    xml = ET.tostring(suite, encoding="utf-8", xml_declaration=True) + b"\n"
    if len(xml) > MAX_JUNIT_BYTES:
        fail("complete campaign JUnit exceeds its byte profile")
    return raw, xml


def publish(
    result: FleetTraceCampaignGate,
    *,
    out: str | Path | None = None,
    junit: str | Path | None = None,
) -> bytes:
    from chimeraforge.api import PlanError
    from chimeraforge.plan_study import protect_output

    try:
        raw, xml = materialize(result)
        outputs = [Path(value) for value in (out, junit) if value is not None]
        for index, path in enumerate(outputs):
            protect_output(path, (*result._input_paths, *outputs[:index], *outputs[index + 1 :]))
        for value, payload in ((out, raw), (junit, xml)):
            if value is not None:
                _write(Path(value), payload)
        return raw
    except (
        PlanError,
        FleetTraceCampaignError,
        OSError,
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        OverflowError,
        RecursionError,
    ) as exc:
        LOG.info("fleet campaign decision output refused (%s)", type(exc).__name__)
        raise PlanError("cannot publish complete fleet campaign decision") from None


def write_fleet_trace_campaign_gate(
    result: FleetTraceCampaignGate,
    *,
    out: str | Path | None = None,
    junit: str | Path | None = None,
) -> None:
    if out is None and junit is None:
        fail("campaign gate output requires a destination")
    publish(result, out=out, junit=junit)
