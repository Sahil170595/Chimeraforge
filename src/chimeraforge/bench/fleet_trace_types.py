"""Public frozen route descriptors and a defensive original-fleet receipt."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path

from chimeraforge.bench.gate_inputs import MAX_TOTAL_BYTES

MAX_ROUTE_BYTES = 1024 * 1024
MAX_FLEET_RECEIPT_BYTES = MAX_TOTAL_BYTES


def _admit_receipt(data: dict) -> None:
    """Bound the existing pretty writer, including its portable newline upper bound."""
    from chimeraforge.api import PlanError

    try:
        encoded = (json.dumps(data, indent=2, allow_nan=False) + "\n").replace("\n", "\r\n")
        if len(encoded.encode("utf-8")) > MAX_FLEET_RECEIPT_BYTES:
            raise ValueError
    except (ValueError, TypeError, OverflowError, RecursionError):
        raise PlanError(
            "original-fleet trace receipt exceeds its bounded writer contract"
        ) from None


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
