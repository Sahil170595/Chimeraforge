"""Closed controls and immutable views for the fixed-configuration exporter."""

from __future__ import annotations

from dataclasses import dataclass
import math

MAX_SNAPSHOT_BYTES = 1024 * 1024
MAX_READINESS_BYTES = 1024
MAX_REQUEST_BYTES = 16 * 1024
MAX_REQUEST_PATH = 2048
STARTUP_POLL_SECONDS = 0.01


class FleetExporterError(ValueError):
    """Invalid configuration or unavailable owned exporter resources."""


@dataclass(frozen=True)
class FleetExporterConfig:
    host: str = "127.0.0.1"
    port: int = 9400
    poll_seconds: float = 15.0
    stale_after_seconds: float = 60.0
    max_clients: int = 16
    startup_seconds: float = 5.0
    shutdown_seconds: int = 5

    def validate(self) -> None:
        if (
            type(self) is not FleetExporterConfig
            or type(self.host) is not str
            or self.host not in ("127.0.0.1", "::1")
        ):
            raise FleetExporterError("exporter requires a numeric loopback host")
        for value, lower, upper in (
            (self.port, 0, 65535),
            (self.max_clients, 2, 64),
            (self.shutdown_seconds, 1, 30),
        ):
            if type(value) is not int or not lower <= value <= upper:
                raise FleetExporterError("invalid exporter integer control")
        for duration, minimum, maximum in (
            (self.poll_seconds, 0.01, 3600),
            (self.stale_after_seconds, 0.01, 86400),
            (self.startup_seconds, 0.1, 30),
        ):
            if (
                type(duration) not in (int, float)
                or not math.isfinite(duration)
                or not minimum <= duration <= maximum
            ):
                raise FleetExporterError("invalid exporter finite time control")


@dataclass(frozen=True)
class FleetExporterSnapshot:
    body: bytes
    state: str
    age_seconds: float | None
    sequence: int
    native_exit_code: int
    original_replicas: int
    published_unix_seconds: float | None
