"""Typed requests and retained results for one explicitly declared endpoint per replica."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from chimeraforge.monitor import MonitorWindow

MAX_ENDPOINTS = 16
MAX_TOTAL_WINDOWS = 256
MAX_REQUESTS = 2048
MAX_BODY_BYTES = 32 * 1024 * 1024
MAX_OBSERVATION_SECONDS = 600.0
MAX_CLEANUP_SECONDS = 10.0
MAX_URL_CHARS = 2048
MAX_ID_CHARS = 64
MAX_MODEL_CHARS = 4096
DEFAULT_BODY_BYTES = 8 * 1024 * 1024


class FleetMonitorError(ValueError):
    """Invalid or unsupported fleet-monitor admission, before observation begins."""


@dataclass(frozen=True)
class FleetEndpoint:
    id: str
    url: str


@dataclass(frozen=True)
class FleetMonitorRequest:
    endpoints: tuple[FleetEndpoint, ...]
    interval: float = 30.0
    windows: int = 1
    timeout: float = 10.0
    observation_seconds: float = 60.0
    cleanup_seconds: float = 2.0
    concurrency: int = 4
    max_requests: int = 256
    max_body_bytes: int = DEFAULT_BODY_BYTES
    ttft_slo: float | None = None
    tpot_slo: float | None = None


@dataclass
class FleetSlot:
    id: str
    url: str
    state: str = "unstarted"
    slo: str = "unknown"
    error: str | None = None
    windows: list[MonitorWindow] = field(default_factory=list)
    observations: list[dict[str, Any]] = field(default_factory=list)
    binding: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FleetMonitorReport:
    backend: str
    model: str
    slots: tuple[FleetSlot, ...]
    plan: dict[str, Any]
    target_sources: dict[str, str]
    budget: dict[str, Any]
    cleanup: dict[str, Any]
    cancelled: bool
    monitor_tool_version: str
    schema_version: int = 1

    @property
    def exit_code(self) -> int:
        if any(
            slot.binding.get(name, {}).get("state") == "mismatch"
            for slot in self.slots
            for name in ("identity", "configuration")
        ):
            return 5
        if any(slot.slo == "breach" for slot in self.slots):
            return 3
        if (
            self.cancelled
            or self.budget["termination"] is not None
            or self.cleanup["state"] != "completed"
            or any(
                slot.state != "complete"
                or slot.slo != "pass"
                or slot.binding.get("identity", {}).get("state") != "matched"
                for slot in self.slots
            )
        ):
            return 4
        return 0

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        complete = sum(slot.state == "complete" for slot in self.slots)
        data["declared_coverage"] = {
            "expected": len(self.slots),
            "complete": complete,
            "state": "complete" if complete == len(self.slots) else "incomplete",
        }
        data["exit_code"] = self.exit_code
        data["outcome"] = {0: "pass", 3: "breach", 4: "unknown", 5: "mismatch"}[self.exit_code]
        data["limits"] = [
            "Coverage describes declared URLs, not distinct processes, GPUs or fleet topology.",
            "No pooled percentiles, capacity, immutable weights or planner accuracy claim.",
            "Metadata brackets are approximate, not atomic snapshots.",
            "Accepted body bytes exclude discarded/in-flight chunks and transport buffers.",
            "Observation and closure deadlines are cooperative, not universal hard-return bounds.",
        ]
        return data
