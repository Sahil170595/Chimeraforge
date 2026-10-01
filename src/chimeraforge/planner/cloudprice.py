"""Hyperscaler on-demand GPU prices, from a dated snapshot of each cloud's list.

`plan --cloud aws|azure` prices a fleet against what that cloud bills on demand
instead of the bundled marketplace rate. A cloud sells instances, not GPUs, so the
bill is computed instance by instance: a TP/PP group has to fit inside one
instance, and a partly-filled instance still bills every GPU in it. The snapshot is
built by ``scripts/build_cloud_prices.py`` and expires like the API price list.
"""

from __future__ import annotations

import datetime as _dt
import json
import math
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources

CLOUDS = ("aws", "azure")
# Same horizon as the hosted-API price snapshot: list prices move.
STALE_AFTER_DAYS = 90


class CloudPriceError(ValueError):
    """A cloud or offer cannot be used."""


@dataclass(frozen=True)
class CloudOffer:
    """One instance size: its GPUs and its on-demand hourly list price."""

    cloud: str
    instance: str
    gpu: str
    gpus: int
    price_per_hour: float
    region: str
    spec_source: str
    price_source: str

    @property
    def price_per_gpu_hour(self) -> float:
        return self.price_per_hour / self.gpus

    def describe(self) -> str:
        return (
            f"{self.cloud} {self.instance} in {self.region} "
            f"(${self.price_per_hour:g}/h for {self.gpus} GPU{'s' if self.gpus != 1 else ''})"
        )


def _today() -> _dt.date:
    return _dt.date.today()


@lru_cache(maxsize=1)
def load_cloud_prices() -> dict:
    """Load the bundled snapshot (packaged via importlib.resources)."""
    try:
        text = (
            resources.files("chimeraforge.planner.data")
            .joinpath("cloud_prices.json")
            .read_text(encoding="utf-8")
        )
    except (FileNotFoundError, ModuleNotFoundError) as exc:  # pragma: no cover
        raise CloudPriceError("bundled cloud_prices.json is missing") from exc
    return json.loads(text)


def offers_for(cloud: str, gpu_name: str) -> list[CloudOffer]:
    """Every whole-GPU instance of ``cloud`` that carries ``gpu_name``."""
    if cloud not in CLOUDS:
        raise CloudPriceError(f"cloud must be one of: {', '.join(CLOUDS)}")
    keys = ("cloud", "instance", "gpu", "gpus", "price_per_hour", "region")
    return [
        CloudOffer(
            **{k: o[k] for k in keys},
            spec_source=o["spec_source"],
            price_source=o["price_source"],
        )
        for o in load_cloud_prices()["offers"]
        if o["cloud"] == cloud and o["gpu"] == gpu_name
    ]


def fleet_hourly_cost(
    offers: list[CloudOffer], n_groups: int, group: int
) -> tuple[float, CloudOffer, int] | None:
    """Cheapest hourly bill for ``n_groups`` groups of ``group`` GPUs each.

    A group (one replica's TP x PP GPUs) cannot span instances, so an instance
    holds floor(gpus / group) groups and the fleet needs
    ceil(n_groups / that) instances, each billed in full. Returns
    (dollars per hour, the instance used, how many), or None when no instance is
    large enough for one group.
    """
    best = None
    for offer in offers:
        per_instance = offer.gpus // max(group, 1)
        if per_instance < 1:
            continue
        count = math.ceil(n_groups / per_instance)
        cost = count * offer.price_per_hour
        if best is None or cost < best[0]:
            best = (cost, offer, count)
    return best


def snapshot_age_days(today: _dt.date | None = None) -> int:
    captured = _dt.date.fromisoformat(load_cloud_prices()["captured_at"])
    return max(((today or _today()) - captured).days, 0)


def is_stale(today: _dt.date | None = None) -> bool:
    return snapshot_age_days(today) > STALE_AFTER_DAYS
