"""Complete population/intent/rollout cases before protected per-file publication."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from xml.etree import ElementTree as ET

from chimeraforge.kubernetes_inspection_types import (
    KIND,
    MAX_JUNIT_BYTES,
    KubernetesInspection,
    KubernetesInspectionError,
    verdict,
)

LOG = logging.getLogger(__name__)


def materialize(result: KubernetesInspection) -> tuple[bytes, bytes]:
    if type(result) is not KubernetesInspection:
        raise KubernetesInspectionError("inspection output requires a typed native result")
    raw = result.json_bytes()
    data = json.loads(raw)
    n = data["plan"]["n_agents"]
    rows = data["resources"]
    if (
        data["kind"] != KIND
        or type(data["schema_version"]) is not int
        or data["schema_version"] != 1
        or type(n) is not int
        or not 1 <= n <= 16
        or len(rows) != 2 * n
        or type(data["exit_code"]) is not int
        or data["exit_code"] != verdict(data)
        or data["state"] != {0: "match", 4: "unavailable", 5: "drift"}.get(data["exit_code"])
    ):
        raise KubernetesInspectionError("invalid finalized inspection population")
    suite = ET.Element(
        "testsuite",
        name="chimeraforge.kubernetes-inspection",
        tests=str(3 * n + 1),
        failures="0",
        errors="0",
        skipped="0",
    )
    errors, failures = 0, 0

    def case(name: str, state: str) -> None:
        nonlocal errors, failures
        node = ET.SubElement(suite, "testcase", classname="kubernetes-inspection", name=name)
        if state in {"missing", "drift"}:
            ET.SubElement(
                node, "failure", type="intent_drift", message="Declared resource intent differs"
            )
            failures += 1
        elif state not in {"match", "complete"}:
            ET.SubElement(
                node,
                "error",
                type="unavailable",
                message="Required native evidence is unavailable or pending",
            )
            errors += 1

    population = (
        "complete"
        if (
            data["preflight"]["complete"]
            and data["budget"]["termination"] is None
            and data["cleanup"]["state"] == "completed"
            and all(row["observation"]["state"] == "complete" for row in rows)
        )
        else "unknown"
    )
    case("original-population", population)
    for index, row in enumerate(rows):
        kind = "Deployment" if index % 2 == 0 else "Service"
        if (
            row["index"] != index
            or type(row["index"]) is not int
            or row["member_index"] != index // 2
            or type(row["member_index"]) is not int
            or row["kind"] != kind
            or row["intent"]["state"] not in {"match", "drift", "missing", "unknown"}
            or row["rollout"]["state"] not in {"complete", "pending", "unknown", "not_requested"}
            or (kind == "Service") != (row["rollout"]["state"] == "not_requested")
        ):
            raise KubernetesInspectionError("invalid original inspection cases")
        case(f"member-{index // 2}.{kind}.intent", row["intent"]["state"])
        if kind == "Deployment":
            case(f"member-{index // 2}.Deployment.rollout", row["rollout"]["state"])
    suite.set("errors", str(errors))
    suite.set("failures", str(failures))
    xml = ET.tostring(suite, encoding="utf-8", xml_declaration=True) + b"\n"
    if len(xml) > MAX_JUNIT_BYTES:
        raise KubernetesInspectionError("complete inspection JUnit exceeds its profile")
    return raw, xml


def publish(
    result: KubernetesInspection,
    *,
    out: str | Path | None = None,
    junit: str | Path | None = None,
) -> bytes:
    from chimeraforge.api import PlanError
    from chimeraforge.bench.fleet_gate_output import _write
    from chimeraforge.plan_study import protect_output

    try:
        if (out is not None or junit is not None) and result._can_publish_files is not True:
            raise KubernetesInspectionError("private input inventory is unverified")
        raw, xml = materialize(result)
        outputs = [Path(value) for value in (out, junit) if value is not None]
        for index, path in enumerate(outputs):
            protect_output(path, (*result._input_paths, *outputs[:index], *outputs[index + 1 :]))
        for destination, payload in ((out, raw), (junit, xml)):
            if destination is not None:
                _write(Path(destination), payload)
        return raw
    except (
        PlanError,
        KubernetesInspectionError,
        OSError,
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        OverflowError,
        RecursionError,
    ) as exc:
        LOG.info("Kubernetes inspection output refused (%s)", type(exc).__name__)
        raise KubernetesInspectionError("cannot publish complete Kubernetes inspection") from None


def write_kubernetes_inspection(
    result: KubernetesInspection,
    *,
    out: str | Path | None = None,
    junit: str | Path | None = None,
) -> None:
    if out is None and junit is None:
        raise KubernetesInspectionError("inspection output requires a destination")
    publish(result, out=out, junit=junit)
