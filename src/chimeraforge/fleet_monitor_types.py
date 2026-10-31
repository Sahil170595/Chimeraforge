"""Typed requests and retained results for one explicitly declared endpoint per replica."""

from __future__ import annotations

from dataclasses import InitVar, dataclass, field
import logging
from pathlib import Path
from typing import Any, cast

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
LOG = logging.getLogger(__name__)


class FleetMonitorError(ValueError):
    """Invalid or unsupported fleet-monitor admission, before observation begins."""


class FleetMonitorExportError(FleetMonitorError):
    """The complete native report cannot fit the supported JSON export profile."""


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
    schema_version: int = 2
    effective_controls: dict[str, Any] | None = None
    _protected_paths: InitVar[tuple[Path, ...]] = ()
    _received_raw: InitVar[bytes | None] = None

    def __post_init__(
        self, _protected_paths: tuple[Path, ...], _received_raw: bytes | None
    ) -> None:
        # InitVars are excluded from fields/asdict; replace retrieves these
        # same-named instance values before calling this constructor again.
        object.__setattr__(self, "_protected_paths", _protected_paths)
        object.__setattr__(self, "_received_raw", _received_raw)

    @property
    def _input_paths(self) -> tuple[Path, ...]:
        return cast(tuple[Path, ...], object.__getattribute__(self, "_protected_paths"))

    @property
    def _held_bytes(self) -> bytes | None:
        return cast(bytes | None, object.__getattribute__(self, "_received_raw"))

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
        from chimeraforge.fleet_monitor_json import report_dict

        return report_dict(self)

    def json_bytes(self) -> bytes:
        from chimeraforge.fleet_monitor_json import encode_public

        return encode_public(self)

    def save(self, path: str | Path) -> None:
        from chimeraforge.api import PlanError
        from chimeraforge.bench.fleet_gate_output import _write
        from chimeraforge.plan_study import protect_output

        raw = self.json_bytes()
        try:
            protect_output(path, self._input_paths)
            _write(Path(path), raw)
        except (PlanError, OSError) as exc:
            LOG.info("fleet JSON output refused (%s)", type(exc).__name__)
            raise FleetMonitorError("cannot publish fleet monitor JSON output") from None
