"""Identities of consumed facts, separate from predictions and performance evidence."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
import hashlib
import json
import math
from pathlib import Path, PureWindowsPath

REPLAY_VERSION = 1


def json_value(value):
    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_value(item) for item in value]
    return value


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(
            json_value(value), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def file_receipt(path: str | Path, raw: bytes) -> dict:
    """The bytes parsed by a loader, never a second read of the same filename."""
    return {
        "kind": "file",
        "path": str(Path(path).resolve()),
        "path_flavor": "windows" if isinstance(Path(path), PureWindowsPath) else "posix",
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def policy_digest() -> str:
    """Hash the in-memory policy tables used alongside the coefficient corpus."""
    from chimeraforge.planner import (
        constants,
        engine,
        evalstats,
        hardware,
        hybrid,
        models,
        provenance,
    )

    facts = {}
    for module in (constants, engine, evalstats, hardware, hybrid, models, provenance):
        rows = {}
        for name, value in vars(module).items():
            if not name.isupper() or name == "GPU_DB":
                continue
            try:
                digest(value)
            except (TypeError, ValueError):
                continue  # classes/functions/sets are covered by the tool version, not a JSON fact
            rows[name] = json_value(value)
        facts[module.__name__] = rows
    return digest(facts)
