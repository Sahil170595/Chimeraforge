"""One complete native campaign snapshot; no child reloading or source resolution."""

from __future__ import annotations

import logging
from pathlib import Path

LOG = logging.getLogger(__name__)
KINDS = {"trace-campaign", "fleet-trace-campaign"}


def hold(source: object, kind: str) -> dict:
    from chimeraforge.api import PlanError
    from chimeraforge.bench.fleet_campaign_receipt import held_campaign
    from chimeraforge.bench.trace_campaign_inputs import load_campaign

    try:
        held: dict = load_campaign(source) if kind == "trace-campaign" else held_campaign(source)
        paths = (*held["protected_paths"], *((held["path"],) if held["path"] else ()))
        held["protected_paths"] = tuple(dict.fromkeys(Path(p).absolute() for p in paths))
        held["byte_basis"] = "held file bytes" if held["path"] else "native object snapshot"
        return held
    except (
        PlanError,
        OSError,
        ValueError,
        TypeError,
        AttributeError,
        OverflowError,
        UnicodeError,
        RecursionError,
    ) as exc:
        LOG.info("Campaign report input refused (%s)", type(exc).__name__)
        raise PlanError("invalid bounded complete campaign report input") from None
