"""Closed descriptive campaign facts, preserving absent observations as unavailable."""

from __future__ import annotations

from chimeraforge.report.trace_view import (
    BINDING_STATES,
    ROW_STATES,
    SLO_STATES,
    TIMES,
    TIMINGS,
    projection as trace_projection,
)


def _declared(manifest: dict, fleet: bool) -> dict:
    descriptors = manifest["ordered_descriptors"]
    assignment: dict[int, int] = {}
    members = []
    if fleet:
        endpoints = {row["id"]: i for i, row in enumerate(manifest["endpoints"], 1)}
        for index, route in enumerate(manifest["routes"]["rows"], 1):
            assignment[index] = endpoints[route["endpoint_id"]]
        members = [
            {
                "ordinal": ordinal,
                "state": "unavailable",
                "rows": [i for i, member in assignment.items() if member == ordinal],
                "slo": "unavailable",
                "bindings": dict.fromkeys(sorted(BINDING_STATES)),
                "latency": "unavailable",
                "declared_only": True,
            }
            for ordinal in range(1, manifest["population"]["original_replicas"] + 1)
        ]
    return {
        "kind": "fleet-trace" if fleet else "trace",
        "sha256": None,
        "size_bytes": None,
        "byte_basis": "no returned native child",
        "fingerprint": None,
        "execution": "unavailable",
        "configuration": "unavailable",
        "cleanup": "unavailable",
        "exit_code": None,
        "clock": "unavailable",
        "counts": {
            "planned": len(descriptors),
            "attempted": None,
            **dict.fromkeys(sorted(ROW_STATES)),
        },
        "concurrency": manifest["controls"]["concurrency"],
        "targets": manifest["controls"]["targets"],
        "goodput": dict.fromkeys(
            ["qualification", "qualified_requests", "horizon_seconds", "requests_per_second"]
        ),
        "joint": dict.fromkeys(sorted(SLO_STATES)),
        "members": members,
        "rows": [
            {
                "ordinal": ordinal,
                "member": assignment.get(ordinal),
                "state": "unavailable",
                "times": dict.fromkeys(TIMES),
                "timing": dict.fromkeys(TIMINGS),
                "tokens": None,
                "cap": "unknown",
                "basis": "unavailable",
                "slo": dict.fromkeys(
                    ("latency_ms", "first_output_ms", "tpot_ms", "joint"), "unknown"
                ),
            }
            for ordinal in range(1, len(descriptors) + 1)
        ],
    }


def projection(held: dict, kind: str) -> dict:
    data = held["data"]
    fleet = kind == "fleet-trace-campaign"
    slots = data["executions"] if fleet else data["replicas"]
    children = held["children"] if fleet else held["replicas"]
    panels = []
    for ordinal, (slot, child) in enumerate(zip(slots, children), 1):
        view = (
            trace_projection(
                {**child, "byte_basis": "embedded serialized child, not original child-file bytes"},
                "fleet-trace" if fleet else "trace",
            )
            if child is not None
            else _declared(data["manifest"], fleet)
        )
        panels.append(
            {
                "ordinal": ordinal,
                "state": slot["state"],
                "start_s": slot["start_s"],
                "end_s": slot["end_s"],
                "native_present": child is not None,
                "view": view,
            }
        )
    return {
        "kind": kind,
        "sha256": held["sha256"],
        "size_bytes": held["size_bytes"],
        "byte_basis": held["byte_basis"],
        "fingerprint": held["fingerprint"],
        "manifest_fingerprint": data["manifest"]["fingerprint"],
        "population": data["manifest"]["population"],
        "execution": data["execution"],
        "state": data["state"],
        "exit_code": data["exit_code"],
        "stop_reason": data["stop_reason"],
        "elapsed_seconds": data["clock"]["elapsed_seconds"],
        "cleanup": data["cleanup"]["state"] if fleet else "not recorded on outer serial campaign",
        "panels": panels,
    }
