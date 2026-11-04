"""Exact bounded public fleet JSON, before any recursive materialization."""

from __future__ import annotations

import json
import logging
from typing import Any, cast

from chimeraforge.fleet_monitor_types import (
    FleetMonitorError,
    FleetMonitorExportError,
    FleetMonitorReport,
    FleetSlot,
)
from chimeraforge.monitor import MetricAssessment, MonitorWindow

MAX_FLEET_JSON_BYTES = 8 * 1024 * 1024
LOG = logging.getLogger(__name__)
LIMITS = [
    "Coverage describes declared URLs, not distinct processes, GPUs or fleet topology.",
    "No pooled percentiles, capacity, immutable weights or planner accuracy claim.",
    "Metadata brackets are approximate, not atomic snapshots.",
    "Accepted body bytes exclude discarded/in-flight chunks and transport buffers.",
    "Observation and closure deadlines are cooperative, not universal hard-return bounds.",
]
PUBLIC_FIELDS = {
    FleetSlot: ("id", "url", "state", "slo", "error", "windows", "observations", "binding"),
    MonitorWindow: ("backend", "model", "seconds", "observed_at", "outcome", "metrics"),
    MetricAssessment: (
        "metric",
        "semantics",
        "target_ms",
        "samples",
        "p95_lower_ms",
        "p95_upper_ms",
        "outcome",
        "confidence",
        "reason",
        "unit",
        "percentile",
    ),
}


def public_projection(value: Any) -> dict[str, Any]:
    """Only named native public fields; private receipt guards never enter JSON."""
    if type(value) is FleetMonitorReport:
        complete = sum(slot.state == "complete" for slot in value.slots)
        result = {
            name: getattr(value, name)
            for name in (
                "backend",
                "model",
                "slots",
                "plan",
                "target_sources",
                "budget",
                "cleanup",
                "cancelled",
                "monitor_tool_version",
                "schema_version",
            )
        }
        if value.schema_version == 2:
            result["effective_controls"] = value.effective_controls
        result["declared_coverage"] = {
            "expected": len(value.slots),
            "complete": complete,
            "state": "complete" if complete == len(value.slots) else "incomplete",
        }
        result["exit_code"] = value.exit_code
        result["outcome"] = {0: "pass", 3: "breach", 4: "unknown", 5: "mismatch"}[value.exit_code]
        result["limits"] = LIMITS
        return result
    fields = PUBLIC_FIELDS.get(type(value))
    if fields is None:
        raise TypeError("unsupported fleet JSON value")
    return {name: getattr(value, name) for name in fields}


def encode_public(value: Any, *, limit: int | None = None) -> bytes:
    """Count exact escaped/indented UTF-8 plus LF, then reuse the admitted bytes.

    This bounds exported traversal/materialization, not earlier native construction
    or the allocation of an individual scalar chunk by the standard JSON encoder.
    """
    encoder = json.JSONEncoder(
        indent=2, ensure_ascii=True, allow_nan=False, default=public_projection
    )
    maximum = MAX_FLEET_JSON_BYTES if limit is None else limit
    output = bytearray()
    try:
        for chunk in encoder.iterencode(value):
            encoded = chunk.encode("utf-8")
            if len(encoded) > maximum - len(output) - 1:
                raise FleetMonitorExportError("fleet monitor JSON export exceeds its byte limit")
            output.extend(encoded)
        output.extend(b"\n")
        return bytes(output)
    except FleetMonitorExportError:
        raise
    except (ValueError, TypeError, OverflowError, RecursionError, UnicodeError) as exc:
        LOG.info("fleet JSON projection refused (%s)", type(exc).__name__)
        raise FleetMonitorError("invalid fleet monitor JSON export") from None


def report_dict(report: FleetMonitorReport) -> dict[str, Any]:
    data = json.loads(encode_public(report))
    # Native safe_observation converts nested tuples to lists; only slots is a tuple.
    data["slots"] = tuple(data["slots"])
    return cast(dict[str, Any], data)
