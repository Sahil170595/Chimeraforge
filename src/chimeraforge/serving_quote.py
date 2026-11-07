"""Dated native whole-instance arithmetic, without placement or capacity claims."""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
import math
from pathlib import Path
import re

from chimeraforge.planner.cloudprice import STALE_AFTER_DAYS
from chimeraforge.serving_declaration import ServingDeclaration, ServingDeclarationError, receive

MAX_BILLING_TARGET_TEXT = 256
MAX_BILLED_INSTANCE_GPUS = 1024  # Bounded native-snapshot input, not a supported topology claim.
MAX_USD_CHARS = 19
_USD = re.compile(r"(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,6})?")


@dataclass(frozen=True)
class ServingQuoteBudgetPolicy:
    """An exact monthly USD cap and optional tightening of the native price age."""

    max_monthly_usd: str
    max_price_age_days: int = STALE_AFTER_DAYS


@dataclass(frozen=True)
class ServingQuote:
    _data: dict

    def to_dict(self) -> dict:
        return copy.deepcopy(self._data)

    @property
    def exit_code(self) -> int:
        return int(self._data.get("exit_code", 0))


def _admit_budget(policy: ServingQuoteBudgetPolicy) -> Decimal:
    if (
        type(policy) is not ServingQuoteBudgetPolicy
        or type(policy.max_monthly_usd) is not str
        or len(policy.max_monthly_usd) > MAX_USD_CHARS
        or not _USD.fullmatch(policy.max_monthly_usd)
        or type(policy.max_price_age_days) is not int
        or not 0 <= policy.max_price_age_days <= STALE_AFTER_DAYS
    ):
        raise ServingDeclarationError("invalid serving quote budget policy")
    return Decimal(policy.max_monthly_usd)


def _usd_text(value: Decimal) -> str:
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _budget(result: dict, cap: Decimal, max_age_days: int) -> None:
    status, reason, exit_code = "unknown", result["reason"], 4
    monthly = None
    if result["status"] == "estimated":
        listed = Decimal(str(result["offer"]["price_per_hour"])).as_tuple()
        exponent = listed.exponent
        assert isinstance(exponent, int)  # Native estimation already admitted a finite price.
        coefficient = int("".join(map(str, listed.digits)))
        scaled = coefficient * result["instance_count"] * result["hours_per_month"]
        # Scaling the decimal coefficient keeps the listed value and caller context exact.
        monthly = Decimal((0, tuple(map(int, str(scaled))), exponent))
        if result["age_days"] > max_age_days:
            status, reason = "stale", "snapshot_too_old"
        elif monthly <= cap:
            status, reason, exit_code = "within_budget", "at_or_below_cap", 0
        else:
            status, reason, exit_code = "above_budget", "above_cap", 5
    result.update(
        schema_version=2,
        exit_code=exit_code,
        budget={
            "status": status,
            "reason": reason,
            "max_monthly_usd": _usd_text(cap),
            "max_price_age_days": max_age_days,
            "quoted_monthly_usd": _usd_text(monthly) if monthly is not None else None,
        },
    )


def quote_serving(
    declaration: ServingDeclaration | str | Path,
    *,
    cloud: str | None = None,
    instance: str | None = None,
    region: str | None = None,
    budget_policy: ServingQuoteBudgetPolicy | None = None,
) -> ServingQuote:
    from chimeraforge.planner.cloudprice import (
        CLOUDS,
        fleet_hourly_cost,
        load_cloud_prices,
        offers_for,
        snapshot_age_days,
    )
    from chimeraforge.planner.constants import HOURS_PER_MONTH
    from chimeraforge.planner.replay import digest

    cap = _admit_budget(budget_policy) if budget_policy is not None else None
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

    def finish() -> ServingQuote:
        if budget_policy is not None and cap is not None:
            _budget(result, cap, budget_policy.max_price_age_days)
        return ServingQuote(result)

    if cloud is None:
        return finish()
    snapshot = copy.deepcopy(load_cloud_prices())
    age_days = snapshot_age_days(snapshot=snapshot)
    result.update(
        captured_at=snapshot["captured_at"],
        age_days=age_days,
        stale=age_days > STALE_AFTER_DAYS,
        snapshot_object_sha256=digest(snapshot),
    )
    rows = [
        row
        for row in snapshot["offers"]
        if row["cloud"] == cloud and row["instance"] == instance and row["region"] == region
    ]
    if len(rows) != 1:
        result["reason"] = "offer_unavailable" if not rows else "offer_ambiguous"
        return finish()
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
        return finish()
    if type(offer.gpus) is not int or not 1 <= offer.gpus <= MAX_BILLED_INSTANCE_GPUS:
        raise ServingDeclarationError("invalid native whole-instance GPU count")
    quoted = fleet_hourly_cost(offers, request.replicas, gpus_per_replica)
    if quoted is None:
        result["reason"] = "group_does_not_fit_instance"
        return finish()
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
    return finish()
