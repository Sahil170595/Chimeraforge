"""Predeclared passive acceptance policy and complete finalized verdict."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, cast


@dataclass(frozen=True)
class FleetMonitorGatePolicy:
    original_replicas: int
    endpoint_ids: tuple[str, ...]
    windows: int
    metrics: dict[str, dict[str, int]]
    baseline: dict[str, Any]
    candidate: dict[str, Any]
    schema_version: int = 1


@dataclass(frozen=True)
class FleetMonitorGate:
    _data: dict[str, Any] = field(repr=False)
    _protected_paths: tuple[Path, ...] = field(default=(), repr=False)

    @property
    def exit_code(self) -> int:
        return int(self._data["exit_code"])

    @property
    def outcome(self) -> str:
        return str(self._data["outcome"])

    @property
    def limits(self) -> str:
        return str(self._data["limits"])

    def json_bytes(self) -> bytes:
        from chimeraforge.api import PlanError
        from chimeraforge.fleet_monitor_json import encode_public
        from chimeraforge.fleet_monitor_types import FleetMonitorError

        try:
            return encode_public(self._data)
        except FleetMonitorError:
            raise PlanError("fleet monitor decision cannot fit the supported JSON export") from None

    def to_dict(self) -> dict[str, Any]:
        return cast(dict[str, Any], json.loads(self.json_bytes()))

    def save(self, path: str | Path) -> None:
        from chimeraforge.fleet_monitor_gate_output import write_fleet_monitor_gate

        write_fleet_monitor_gate(self, out=path)
