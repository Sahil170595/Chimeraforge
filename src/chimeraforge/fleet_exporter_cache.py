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
from chimeraforge.fleet_monitor_types import FleetMonitorReport

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
class _Entry:
    body: bytes
    stale_body: bytes
    state: str
    sequence: int
    code: int
    monotonic: float | None
    wall: float | None


class SnapshotCache:
    def __init__(self, unavailable: FleetMonitorReport, ttl: float) -> None:
        self._template, self._ttl = unavailable, ttl
        self._lock = threading.Lock()
        body = _body(unavailable, "initial", 0, None, ttl)
        self._entry = _Entry(body, body, "initial", 0, 4, None, None)

    def publish(self, report: FleetMonitorReport | None, state: str = "fresh") -> None:
        with self._lock:
            sequence = self._entry.sequence + 1
        wall, monotonic = time.time(), time.monotonic()
        selected = report if report is not None else self._template
        body = _body(selected, state, sequence, wall, self._ttl)
        stale = _body(self._template, "stale", sequence, wall, self._ttl)
        entry = _Entry(body, stale, state, sequence, selected.exit_code, monotonic, wall)
        with self._lock:
            self._entry = entry

    def snapshot(self) -> FleetExporterSnapshot:
        with self._lock:
            entry = self._entry
        age = max(0.0, time.monotonic() - entry.monotonic) if entry.monotonic is not None else None
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
