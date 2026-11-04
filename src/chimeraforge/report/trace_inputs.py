"""One strict native snapshot, with bounded public input traversal before copying."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import cast

from chimeraforge.bench.fleet_trace_types import FleetTraceReplay
from chimeraforge.bench.gate_inputs import MAX_RECEIPT_BYTES, MAX_TOTAL_BYTES
from chimeraforge.bench.trace import TraceReplay

LOG = logging.getLogger(__name__)


def hold(source: object, kind: str) -> dict:
    from chimeraforge.api import PlanError
    from chimeraforge.bench.fleet_trace_receipt import _held_fleet_trace
    from chimeraforge.bench.trace_gate_inputs import load_trace

    try:
        limit = MAX_RECEIPT_BYTES if kind == "trace" else MAX_TOTAL_BYTES
        expected = TraceReplay if kind == "trace" else FleetTraceReplay
        protected: tuple[Path, ...] = ()
        if isinstance(source, expected):
            protected = tuple(Path(p).absolute() for p in source._protected_paths)
            value = source._data
        else:
            value = source
        if type(value) is dict:
            size = 0
            for chunk in json.JSONEncoder(allow_nan=False, ensure_ascii=True).iterencode(value):
                size += len(chunk.encode("utf-8"))
                if size > limit:
                    raise ValueError("native input profile exceeded")
        elif not isinstance(value, (str, Path)):
            raise ValueError("unsupported native input")
        held = load_trace(value) if kind == "trace" else _held_fleet_trace(value)
        paths = (*protected, *held["protected_paths"], *((held["path"],) if held["path"] else ()))
        held["protected_paths"] = tuple(dict.fromkeys(Path(p).absolute() for p in paths))
        held["byte_basis"] = "held file bytes" if held["path"] else "native object snapshot"
        return cast(dict, held)
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
        LOG.info("Trace report input refused (%s)", type(exc).__name__)
        raise PlanError("invalid bounded trace report input") from None
