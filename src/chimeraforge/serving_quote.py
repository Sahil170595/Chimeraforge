"""Dated native whole-instance arithmetic, without placement or capacity claims."""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import math
from pathlib import Path

from chimeraforge.serving_declaration import ServingDeclaration, ServingDeclarationError, receive

MAX_BILLING_TARGET_TEXT = 256
MAX_BILLED_INSTANCE_GPUS = 1024  # Bounded native-snapshot input, not a supported topology claim.


@dataclass(frozen=True)
class ServingQuote:
    _data: dict

    def to_dict(self) -> dict:
        return copy.deepcopy(self._data)


def quote_serving(
    declaration: ServingDeclaration | str | Path,
    *,
    cloud: str | None = None,
    instance: str | None = None,
    region: str | None = None,
) -> ServingQuote:
    from chimeraforge.planner.cloudprice import (
        CLOUDS,
        fleet_hourly_cost,
        load_cloud_prices,
        offers_for,
        snapshot_age_days,
        STALE_AFTER_DAYS,
    )
    from chimeraforge.planner.constants import HOURS_PER_MONTH
    from chimeraforge.planner.replay import digest

    held = receive(declaration)
    request = held.request
    gpus_per_replica = request.tensor_parallel * request.pipeline_parallel
    logical_gpu_slots = request.replicas * gpus_per_replica
    target = (cloud, instance, region)
    if any(value is not None for value in target) and (
        any(
            type(value) is not str or not 1 <= len(value) <= MAX_BILLING_TARGET_TEXT
            for value in target
        )
        or cloud not in CLOUDS
    ):
        raise ServingDeclarationError(
            "quote requires all of cloud, exact instance and exact region"
        )
    result = {
        "schema_version": 1,
        "kind": "chimeraforge.serving-quote",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "declaration_fingerprint": held.fingerprint,
        "status": "unknown",
        "reason": "no_billing_target",
        "replicas": request.replicas,
        "gpus_per_replica": gpus_per_replica,
        "logical_gpu_slots": logical_gpu_slots,
        "cloud": cloud,
        "instance": instance,
        "region": region,
        "offer": None,
        "instance_count": None,
        "billed_gpus": None,
        "idle_billed_gpus": None,
        "price_per_hour": None,
        "monthly_cost": None,
        "hours_per_month": HOURS_PER_MONTH,
        "captured_at": None,
        "age_days": None,
        "stale": None,
        "snapshot_object_sha256": None,
        "feasibility": None,
        "throughput_tps": None,
        "quality": None,
        "cost_per_token": None,
        "deployment_ready": None,
        "allocation_basis": (
            "Native homogeneous whole-instance arithmetic: complete TP*PP groups per instance; "
            "no cross-instance group splitting."
        ),
        "placement": (
            "Unverified; quote arithmetic assigns no replica, host, GPU identity, "
            "Compose project or running capacity."
        ),
    }
    if cloud is None:
        return ServingQuote(result)
    snapshot = copy.deepcopy(load_cloud_prices())
    result.update(
        captured_at=snapshot["captured_at"],
        age_days=snapshot_age_days(snapshot=snapshot),
        stale=snapshot_age_days(snapshot=snapshot) > STALE_AFTER_DAYS,
        snapshot_object_sha256=digest(snapshot),
    )
    rows = [
        row
        for row in snapshot["offers"]
        if row["cloud"] == cloud and row["instance"] == instance and row["region"] == region
    ]
    if len(rows) != 1:
        result["reason"] = "offer_unavailable" if not rows else "offer_ambiguous"
        return ServingQuote(result)
    row = rows[0]
    offers = [
        offer
        for offer in offers_for(cloud, row["gpu"], snapshot=snapshot)
        if offer.instance == instance and offer.region == region
    ]
    if len(offers) != 1:
        raise ServingDeclarationError("ambiguous native billing offer")
    offer = offers[0]
    result["offer"] = asdict(offer)
    if (
        type(offer.price_per_hour) not in (int, float)
        or not math.isfinite(offer.price_per_hour)
        or offer.price_per_hour <= 0
    ):
        result["reason"] = "price_unknown"
        return ServingQuote(result)
    if type(offer.gpus) is not int or not 1 <= offer.gpus <= MAX_BILLED_INSTANCE_GPUS:
        raise ServingDeclarationError("invalid native whole-instance GPU count")
    quoted = fleet_hourly_cost(offers, request.replicas, gpus_per_replica)
    if quoted is None:
        result["reason"] = "group_does_not_fit_instance"
        return ServingQuote(result)
    hourly, _, count = quoted
    monthly = hourly * HOURS_PER_MONTH
    if not math.isfinite(monthly):
        raise ServingDeclarationError("native quote arithmetic overflow")
    result.update(
        status="estimated",
        reason="dated_whole_instance_arithmetic",
        instance_count=count,
        billed_gpus=count * offer.gpus,
        idle_billed_gpus=count * offer.gpus - logical_gpu_slots,
        price_per_hour=hourly,
        monthly_cost=monthly,
    )
    return ServingQuote(result)
