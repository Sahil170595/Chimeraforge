"""Protected native JSON and closed ordinal JUnit for one frozen inventory census."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from xml.etree import ElementTree as ET

from chimeraforge.bench.fleet_gate_output import MAX_JUNIT_BYTES, _write
from chimeraforge.bench.gate_inputs import sha
from chimeraforge.deploy import MAX_EXPORT_GPUS_PER_REPLICA
from chimeraforge.inventory_types import (
    InventoryBaseline,
    InventoryCaptureObservation,
    InventoryCheck,
    InventoryDevice,
    InventoryObservation,
    InventorySlot,
    SelectedBatchBaseline,
)
from chimeraforge.planner.constants import MAX_REPLICAS

LOG = logging.getLogger(__name__)
BELOW = {"below_saved_baseline", "below_selected_batch_estimate"}


def _validate(result: InventoryCheck) -> tuple[int, int]:
    from chimeraforge.api import PlanError

    if type(result) is not InventoryCheck:
        raise PlanError("inventory output requires a finalized inventory check")
    capture = type(result.observation) is InventoryCaptureObservation
    selected = type(result.baseline) is SelectedBatchBaseline
    prefix = "supplied" if capture else "queried"
    suffix = "selected_batch_memory" if selected else "saved_b1_memory"
    if (
        type(result.observation) not in (InventoryObservation, InventoryCaptureObservation)
        or type(result.baseline) not in (InventoryBaseline, SelectedBatchBaseline)
        or type(result.schema_version) is not int
        or result.schema_version != (3 if capture else 2 if selected else 1)
        or result.scope != prefix + "_inventory_and_" + suffix
        or not sha(result.plan_fingerprint)
        or type(result.candidate_index) is not int
        or result.candidate_index < 0
        or result.observation.state not in ("complete", "unknown", "not_started")
        or type(result.slots) is not tuple
        or type(result.observation.devices) is not tuple
        or any(type(device) is not InventoryDevice for device in result.observation.devices)
        or result.deployment_ready is not None
    ):
        raise PlanError("invalid finalized inventory output")
    if isinstance(
        result.observation, InventoryObservation
    ) and result.observation.cleanup_state not in ("completed", "not_started", "failed"):
        raise PlanError("invalid inventory cleanup evidence")
    population = result._declared_population
    if population is None:
        if result.slots:
            raise PlanError("inventory output needs the admitted original census")
        replicas, devices = 0, 0
    else:
        if (
            type(population) is not tuple
            or len(population) != 3
            or any(type(value) is not int or value < 1 for value in population)
        ):
            raise PlanError("invalid original inventory dimensions")
        replicas, tp, pp = population
        devices = tp * pp
        if replicas > MAX_REPLICAS or devices > MAX_EXPORT_GPUS_PER_REPLICA:
            raise PlanError("original inventory dimensions exceed native bounds")
    if len(result.slots) != replicas * devices:
        raise PlanError("inventory output must retain the whole original census")
    comparisons = (
        {"unknown", "at_least_selected_batch_estimate", "below_selected_batch_estimate"}
        if selected
        else {"unknown", "at_least_saved_baseline", "below_saved_baseline"}
    )
    for index, slot in enumerate(result.slots):
        if (
            type(slot) is not InventorySlot
            or type(slot.replica_index) is not int
            or slot.replica_index != index // devices
            or type(slot.device_index) is not int
            or slot.device_index != index % devices
            or slot.selector_state not in ("present", "absent", "unknown")
            or slot.free_comparison not in comparisons
            or slot.total_comparison not in comparisons
            or (
                type(slot.device) is not InventoryDevice
                if slot.selector_state == "present"
                else slot.device is not None
            )
        ):
            raise PlanError("invalid original inventory slot population")
    if type(result._protected_paths) is not tuple or any(
        not isinstance(path, Path) or not path.is_absolute() for path in result._protected_paths
    ):
        raise PlanError("invalid private inventory source roles")
    return replicas, devices


def _materialize(
    result: InventoryCheck, *, want_json: bool, want_junit: bool
) -> tuple[bytes | None, bytes | None]:
    from chimeraforge.api import PlanError

    replicas, devices = _validate(result)
    raw = (
        (json.dumps(result.to_dict(), indent=2, allow_nan=False) + "\n").encode()
        if want_json
        else None
    )
    if not want_junit:
        return raw, None
    observation = result.observation
    incomplete = observation.state != "complete" or (
        isinstance(observation, InventoryObservation) and observation.cleanup_state != "completed"
    )
    states = [
        (
            incomplete
            or slot.selector_state == "unknown"
            or slot.selector_state == "present"
            and slot.free_comparison == "unknown",
            slot.selector_state == "absent" or slot.free_comparison in BELOW,
        )
        for slot in result.slots
    ]
    suite = ET.Element(
        "testsuite",
        name="chimeraforge.inventory-check",
        tests=str(2 + replicas + len(result.slots)),
        failures="0",
        errors="0",
        skipped="0",
    )
    errors, failures = 0, 0

    def case(name: str, error: bool, failure: bool, properties: dict) -> None:
        nonlocal errors, failures
        node = ET.SubElement(suite, "testcase", name=name, classname="inventory-check")
        props = ET.SubElement(node, "properties")
        for key, value in properties.items():
            ET.SubElement(props, "property", name=key, value=str(value))
        if error:
            ET.SubElement(
                node,
                "error",
                type="unknown",
                message="Required inventory evidence is incomplete or unknown",
            )
            errors += 1
        if failure:
            ET.SubElement(
                node,
                "failure",
                type="memory-mismatch",
                message=(
                    "Declared selector is absent or reported free memory is below "
                    "the saved comparison"
                ),
            )
            failures += 1

    case(
        "overall",
        incomplete or not states or any(error for error, _ in states),
        any(failure for _, failure in states),
        {
            "exit_code": result.exit_code,
            "plan_fingerprint": result.plan_fingerprint,
            "memory_basis": "selected-batch"
            if isinstance(result.baseline, SelectedBatchBaseline)
            else "batch-one",
            "replicas": replicas,
            "expected_slots": len(result.slots),
        },
    )
    properties = {
        "state": observation.state,
        "source": "supplied" if isinstance(observation, InventoryCaptureObservation) else "queried",
    }
    evidence = (
        observation.capture_sha256
        if isinstance(observation, InventoryCaptureObservation)
        else observation.stdout_sha256
    )
    if evidence is not None:
        if not sha(evidence):
            raise PlanError("invalid inventory evidence digest")
        properties["evidence_sha256"] = evidence
    if isinstance(observation, InventoryObservation):
        properties["cleanup_state"] = observation.cleanup_state
    case("observation", incomplete, False, properties)
    for replica in range(replicas):
        selected_states = states[replica * devices : (replica + 1) * devices]
        case(
            f"replica-{replica}",
            any(error for error, _ in selected_states),
            any(failure for _, failure in selected_states),
            {"replica_index": replica, "devices": devices},
        )
        for index in range(devices):
            slot = result.slots[replica * devices + index]
            error, failure = selected_states[index]
            case(
                f"replica-{replica}.device-{index}",
                error,
                failure,
                {
                    "replica_index": replica,
                    "device_index": index,
                    "selector_state": slot.selector_state,
                    "free_comparison": slot.free_comparison,
                    "total_comparison": slot.total_comparison,
                },
            )
    suite.set("errors", str(errors))
    suite.set("failures", str(failures))
    xml = ET.tostring(suite, encoding="utf-8", xml_declaration=True) + b"\n"
    if len(xml) > MAX_JUNIT_BYTES:
        raise PlanError("complete inventory JUnit exceeds its byte profile")
    return raw, xml


def write_inventory_check(
    result: InventoryCheck, *, out: str | Path | None = None, junit: str | Path | None = None
) -> None:
    """Admit all requested buffers before separately atomic protected writes."""
    from chimeraforge.api import PlanError
    from chimeraforge.commands._trace_output import preflight_trace_output
    from chimeraforge.plan_study import protect_output

    if out is None and junit is None:
        raise PlanError("inventory output requires a destination")
    try:
        raw, xml = _materialize(result, want_json=out is not None, want_junit=junit is not None)
        outputs = [Path(value) for value in (out, junit) if value is not None]
        for index, path in enumerate(outputs):
            protect_output(
                path, (*result._protected_paths, *outputs[:index], *outputs[index + 1 :])
            )
            preflight_trace_output(path, create_parents=True)
        for destination, payload in ((out, raw), (junit, xml)):
            if destination is not None:
                assert payload is not None
                _write(Path(destination), payload)
    except (
        PlanError,
        OSError,
        ValueError,
        TypeError,
        AttributeError,
        KeyError,
        OverflowError,
        RecursionError,
    ) as exc:
        LOG.info("inventory output refused (%s)", type(exc).__name__)
        raise PlanError("cannot publish complete inventory check") from None
