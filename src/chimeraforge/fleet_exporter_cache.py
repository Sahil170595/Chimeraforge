"""Native gauges projected to safe labels, then published as immutable bytes."""

from __future__ import annotations

from dataclasses import dataclass, replace
import threading
import time

from chimeraforge.fleet_exporter_types import (
    FleetExporterError,
    FleetExporterSnapshot,
    MAX_SNAPSHOT_BYTES,
)
from chimeraforge.fleet_monitor_output import prometheus_text
from chimeraforge.fleet_monitor_types import FleetMonitorReport, FleetSlot

STATES = ("initial", "fresh", "stale", "unavailable", "stopped")


def _body(
    report: FleetMonitorReport, state: str, sequence: int, wall: float | None, ttl: float
) -> bytes:
    public = replace(
        report,
        model="configured",
        slots=tuple(replace(slot, id=f"replica-{i + 1}") for i, slot in enumerate(report.slots)),
    )
    rows = [prometheus_text(public).rstrip()]
    for name, description in (
        ("snapshot_state", "Freshness state of cached client observations."),
        ("snapshot_sequence", "Number of cache publications, not traffic."),
        ("declared_replicas", "Original configured population, not physical independence."),
        ("stale_after_seconds", "Monotonic cache expiry allowance."),
        (
            "last_publication_timestamp_seconds",
            "Local wall clock at publication, not authentication.",
        ),
    ):
        rows.extend(
            [
                f"# HELP chimeraforge_exporter_{name} {description}",
                f"# TYPE chimeraforge_exporter_{name} gauge",
            ]
        )
    rows.extend(
        f'chimeraforge_exporter_snapshot_state{{state="{value}"}} {int(state == value)}'
        for value in STATES
    )
    rows.extend(
        [
            f"chimeraforge_exporter_snapshot_sequence {sequence}",
            f"chimeraforge_exporter_declared_replicas {len(report.slots)}",
            f"chimeraforge_exporter_stale_after_seconds {ttl:g}",
        ]
    )
    if wall is not None:
        rows.append(f"chimeraforge_exporter_last_publication_timestamp_seconds {wall:.6f}")
    raw = ("\n".join(rows) + "\n").encode("utf-8")
    if len(raw) > MAX_SNAPSHOT_BYTES:
        raise FleetExporterError("complete exporter snapshot exceeds byte bound")
    return raw


@dataclass(frozen=True)
class _ObservationFact:
    expected: int
    observed: int
    bound: bool


@dataclass(frozen=True)
class _PopulationBinding:
    backend: str
    model: str
    endpoints: tuple[tuple[str, str], ...]
    plan: dict
    monitor_version: str
    controls: dict
    target_sources: dict

    def observe(self, report: FleetMonitorReport | None, state: str) -> _ObservationFact | None:
        from chimeraforge.fleet_monitor_receipt import same

        if report is None or type(report) is not FleetMonitorReport or state != "fresh":
            return None
        slots = report.slots
        observed = len(slots) if type(slots) is tuple else 0
        bound = (
            type(slots) is tuple
            and observed == len(self.endpoints)
            and all(type(slot) is FleetSlot for slot in slots)
            and same(tuple((slot.id, slot.url) for slot in slots), self.endpoints, exact_types=True)
            and same(report.backend, self.backend, exact_types=True)
            and same(report.model, self.model, exact_types=True)
            and same(report.plan, self.plan, exact_types=True)
            and same(report.monitor_tool_version, self.monitor_version, exact_types=True)
            and same(report.schema_version, 2, exact_types=True)
            and same(report.effective_controls, self.controls, exact_types=True)
            and same(report.target_sources, self.target_sources, exact_types=True)
        )
        return _ObservationFact(len(self.endpoints), observed, bound)


@dataclass(frozen=True)
class _Entry:
    body: bytes
    stale_body: bytes
    state: str
    sequence: int
    code: int
    monotonic: float | None
    wall: float | None
    observation: _ObservationFact | None = None


@dataclass(frozen=True)
class _CapturedSnapshot:
    snapshot: FleetExporterSnapshot
    observation: _ObservationFact | None
    raw_age: float | None
    native_code: int
    expected: int
    ttl: float


class SnapshotCache:
    def __init__(
        self,
        unavailable: FleetMonitorReport,
        ttl: float,
        *,
        binding: _PopulationBinding | None = None,
    ) -> None:
        self._template, self._ttl = unavailable, ttl
        self._binding = binding
        self._lock = threading.Lock()
        body = _body(unavailable, "initial", 0, None, ttl)
        self._entry = _Entry(body, body, "initial", 0, 4, None, None)

    def publish(self, report: FleetMonitorReport | None, state: str = "fresh") -> None:
        with self._lock:
            sequence = self._entry.sequence + 1
        wall, monotonic = time.time(), time.monotonic()
        selected = report if report is not None else self._template
        observation = self._binding.observe(report, state) if self._binding is not None else None
        body = _body(selected, state, sequence, wall, self._ttl)
        stale = _body(self._template, "stale", sequence, wall, self._ttl)
        entry = _Entry(
            body, stale, state, sequence, selected.exit_code, monotonic, wall, observation
        )
        with self._lock:
            self._entry = entry

    def snapshot(self) -> FleetExporterSnapshot:
        with self._lock:
            entry = self._entry
        raw_age = time.monotonic() - entry.monotonic if entry.monotonic is not None else None
        return self._view(entry, raw_age)

    def _view(self, entry: _Entry, raw_age: float | None) -> FleetExporterSnapshot:
        age = max(0.0, raw_age) if raw_age is not None else None
        expired = age is not None and age >= self._ttl and entry.state not in ("stopped",)
        return FleetExporterSnapshot(
            entry.stale_body if expired else entry.body,
            "stale" if expired else entry.state,
            age,
            entry.sequence,
            4 if expired else entry.code,
            len(self._template.slots),
            entry.wall,
        )

    def _capture(self) -> _CapturedSnapshot:
        with self._lock:
            entry = self._entry
            raw_age = time.monotonic() - entry.monotonic if entry.monotonic is not None else None
            return _CapturedSnapshot(
                self._view(entry, raw_age),
                entry.observation,
                raw_age,
                entry.code,
                len(self._binding.endpoints) if self._binding is not None else 0,
                self._ttl,
            )
