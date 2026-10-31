"""Complete fleet-campaign public data with an explicit bounded export profile."""

from __future__ import annotations

from dataclasses import InitVar, dataclass, field
import hashlib
import json
import logging
from pathlib import Path
from typing import Any, cast

from chimeraforge.bench.fleet_gate_inputs import FleetTraceGatePolicy

MAX_CAMPAIGN_BYTES = 16 * 1024 * 1024
MAX_PAIR_BYTES = 32 * 1024 * 1024
MAX_POLICY_BYTES = 64 * 1024
KIND = "chimeraforge.fleet-trace-campaign"
MANIFEST_KIND = KIND + "-manifest"
CAMPAIGN_LIMITS = (
    "K serial whole-fleet executions retain original N/routes/global schedule/C. "
    "No retries, survivor selection, pooling, cold/independent/GPU/performance authentication. "
    "Campaign deadline bounds admission/signalling; native cleanup remains cooperative. "
    "Native child 32MiB contract remains; absent returned receipts leave completion unknown. "
    "16MiB export profile bounds new exported buffers/traversal, "
    "not prior construction/heap/scalar chunks. "
    "Plan intent and declared URLs may be private; treat receipts like their input plans."
)
LOG = logging.getLogger(__name__)


class FleetTraceCampaignError(ValueError):
    """A complete campaign cannot be represented in its declared byte profile."""


def canonical_hash(value: Any) -> str:
    """Native digest parity on this closed finite/plain JSON family, without a copy."""
    result = hashlib.sha256()
    encoder = json.JSONEncoder(
        sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    )
    for chunk in encoder.iterencode(value):
        result.update(chunk.encode("utf-8"))
    return result.hexdigest()


def encoded_data(value: Any, limit: int | None = None) -> bytes:
    """Bound exact exported ASCII/UTF-8 chunks and LF, not prior construction/heap."""
    output = bytearray()
    maximum = MAX_CAMPAIGN_BYTES if limit is None else limit
    try:
        encoder = json.JSONEncoder(indent=2, ensure_ascii=True, allow_nan=False)
        for chunk in encoder.iterencode(value):
            raw = chunk.encode("utf-8")
            if len(raw) > maximum - len(output) - 1:
                raise FleetTraceCampaignError("fleet campaign JSON exceeds its byte profile")
            output.extend(raw)
        output.extend(b"\n")
        return bytes(output)
    except FleetTraceCampaignError:
        raise
    except (TypeError, ValueError, OverflowError, RecursionError, UnicodeError) as exc:
        LOG.info("fleet campaign JSON refused (%s)", type(exc).__name__)
        raise FleetTraceCampaignError("invalid fleet campaign JSON") from None


@dataclass(frozen=True)
class FleetTraceCampaign:
    """Every declared execution, including failed/unstarted slots, remains available."""

    _data: dict = field(repr=False)
    _protected_paths: InitVar[tuple[Path, ...]] = ()

    def __post_init__(self, _protected_paths: tuple[Path, ...]) -> None:
        object.__setattr__(self, "_protected_paths", _protected_paths)

    @property
    def _input_paths(self) -> tuple[Path, ...]:
        return cast(tuple[Path, ...], object.__getattribute__(self, "_protected_paths"))

    @property
    def exit_code(self) -> int:
        return int(self._data["exit_code"])

    @property
    def state(self) -> str:
        return str(self._data["state"])

    def json_bytes(self) -> bytes:
        return encoded_data(self._data)

    def to_dict(self) -> dict:
        return cast(dict, json.loads(self.json_bytes()))

    def save(self, path: str | Path) -> None:
        from chimeraforge.api import PlanError
        from chimeraforge.bench.fleet_gate_output import _write
        from chimeraforge.plan_study import protect_output

        raw = self.json_bytes()
        try:
            protect_output(path, self._input_paths)
            _write(Path(path), raw)
        except (PlanError, OSError) as exc:
            LOG.info("fleet campaign output refused (%s)", type(exc).__name__)
            raise PlanError("cannot publish fleet campaign output") from None


@dataclass(frozen=True)
class FleetTraceCampaignGatePolicy:
    """Outer K/budget commitment over an unchanged one-fleet native policy."""

    fleet: FleetTraceGatePolicy
    expected_executions: int
    campaign_timeout_seconds: float
    schema_version: int = 1


@dataclass(frozen=True)
class FleetTraceCampaignGate:
    """One finalized full-population decision, with private output guards."""

    _data: dict = field(repr=False)
    _protected_paths: InitVar[tuple[Path, ...]] = ()

    def __post_init__(self, _protected_paths: tuple[Path, ...]) -> None:
        object.__setattr__(self, "_protected_paths", _protected_paths)

    @property
    def _input_paths(self) -> tuple[Path, ...]:
        return cast(tuple[Path, ...], object.__getattribute__(self, "_protected_paths"))

    @property
    def exit_code(self) -> int:
        return int(self._data["exit_code"])

    def json_bytes(self) -> bytes:
        return encoded_data(self._data, MAX_PAIR_BYTES)

    def to_dict(self) -> dict:
        return cast(dict, json.loads(self.json_bytes()))

    def save(self, path: str | Path) -> None:
        from chimeraforge.bench.fleet_campaign_output import write_fleet_trace_campaign_gate

        write_fleet_trace_campaign_gate(self, out=path)
