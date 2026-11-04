"""Public frozen route descriptors and a defensive original-fleet receipt."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path

from chimeraforge.bench.gate_inputs import MAX_TOTAL_BYTES

MAX_ROUTE_BYTES = 1024 * 1024
MAX_FLEET_RECEIPT_BYTES = MAX_TOTAL_BYTES


def _admit_receipt(data: dict, limit: int | None = None) -> None:
    """Bound the existing pretty writer, including its portable newline upper bound."""
    from chimeraforge.api import PlanError

    # Resolve the outer bound now; explicit child profiles retain their own limits.
    maximum = MAX_FLEET_RECEIPT_BYTES if limit is None else limit
    try:
        if type(maximum) is not int or not 0 < maximum <= MAX_TOTAL_BYTES:
            raise ValueError
        remaining = maximum - 2  # The existing writer's final newline, portably CRLF.
        for chunk in json.JSONEncoder(indent=2, allow_nan=False).iterencode(data):
            size = len(chunk.replace("\n", "\r\n").encode("utf-8"))
            if size > remaining:
                raise ValueError
            remaining -= size
    except (ValueError, TypeError, OverflowError, RecursionError):
        message = (
            "original-fleet trace receipt exceeds its bounded writer contract"
            if maximum == MAX_FLEET_RECEIPT_BYTES
            else "trace receipt exceeds its bounded writer byte limit"
        )
        raise PlanError(message) from None


@dataclass(frozen=True)
class TraceRoute:
    request_id: str
    endpoint_id: str


@dataclass(frozen=True)
class FleetTraceReplay:
    """One global row population; member views contain row references only."""

    _data: dict = field(repr=False)
    _protected_paths: tuple[Path, ...] = field(default=(), repr=False)

    def to_dict(self) -> dict:
        from chimeraforge.bench.fleet_trace_receipt import native_projection

        _admit_receipt(self._data)
        if type(self._data.get("native_trace")) is dict:
            native_projection(self._data["native_trace"])
        return copy.deepcopy(self._data)

    @property
    def exit_code(self) -> int:
        return int(self._data["exit_code"])

    def save(self, path: str | Path) -> None:
        from chimeraforge.api import PlanArtifact
        from chimeraforge.plan_study import protect_output

        protect_output(path, self._protected_paths)
        _admit_receipt(self._data)
        PlanArtifact(self.to_dict()).save(path)
