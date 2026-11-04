"""Complete public inspection facts; runtime input identities are not data fields."""

from __future__ import annotations

from dataclasses import InitVar, dataclass, field
import json
import logging
from pathlib import Path
from typing import Any, cast

MAX_REPORT_BYTES = 1024 * 1024
MAX_JUNIT_BYTES = 64 * 1024
KIND = "chimeraforge.kubernetes-inspection"
LOG = logging.getLogger(__name__)


class KubernetesInspectionError(ValueError):
    """Invalid independent intent or unsafe/unrepresentable inspection output."""


def verdict(data: dict) -> int:
    rows = data["resources"]
    if any(row["intent"]["state"] in {"missing", "drift"} for row in rows):
        return 5
    if (
        data["budget"]["termination"] is not None
        or data["cleanup"]["state"] != "completed"
        or not data["preflight"]["complete"]
        or any(
            row["intent"]["state"] != "match"
            or row["rollout"]["state"] not in {"complete", "not_requested"}
            for row in rows
        )
    ):
        return 4
    return 0


@dataclass(frozen=True)
class KubernetesInspection:
    """All original resources remain inspectable even if bounded export refuses."""

    _data: dict = field(repr=False)
    _protected_paths: InitVar[tuple[Path, ...]] = ()
    _private_inventory_verified: InitVar[bool] = False

    def __post_init__(
        self, _protected_paths: tuple[Path, ...], _private_inventory_verified: bool
    ) -> None:
        object.__setattr__(self, "_protected_paths", _protected_paths)
        object.__setattr__(self, "_private_inventory_verified", _private_inventory_verified)

    @property
    def _input_paths(self) -> tuple[Path, ...]:
        return cast(tuple[Path, ...], object.__getattribute__(self, "_protected_paths"))

    @property
    def _can_publish_files(self) -> bool:
        return cast(bool, object.__getattribute__(self, "_private_inventory_verified"))

    @property
    def exit_code(self) -> int:
        return int(self._data["exit_code"])

    @property
    def resources(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._data["resources"])

    def json_bytes(self) -> bytes:
        from chimeraforge.bench.fleet_campaign_types import encoded_data

        try:
            return encoded_data(self._data, MAX_REPORT_BYTES)
        except (ValueError, TypeError, OverflowError, RecursionError) as exc:
            LOG.info("complete Kubernetes inspection JSON refused (%s)", type(exc).__name__)
            raise KubernetesInspectionError(
                "complete inspection JSON exceeds its profile"
            ) from None

    def to_dict(self) -> dict[str, Any]:
        return cast(dict[str, Any], json.loads(self.json_bytes()))

    def save(self, path: str | Path) -> None:
        from chimeraforge.kubernetes_inspection_output import publish

        publish(self, out=path)
