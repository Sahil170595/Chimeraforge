"""Which serving engines run on which platform, per each engine's own docs.

Reads ``data/engine_support.json`` (built by scripts/build_engine_support.py).
Every claim carries a verbatim quote and a URL pinned to the engine release it
was read at; "not documented" is silence, never a verdict. Engines move fast,
so the snapshot declares its age and warns past :data:`MAX_AGE_DAYS`.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files

# Engine release cadence is weeks; a quarter-old snapshot is past trusting.
MAX_AGE_DAYS = 90

PLATFORM_LINUX_CUDA = "linux-cuda"
PLATFORM_LINUX_ROCM = "linux-rocm"
PLATFORM_LINUX_XPU = "linux-xpu"
PLATFORM_WINDOWS = "windows-native"
PLATFORM_WSL2 = "windows-wsl2"
PLATFORM_MACOS = "macos-apple-silicon"
PLATFORM_CPU = "cpu"

STATUS_SUPPORTED = "supported"
STATUS_EXPERIMENTAL = "experimental"
STATUS_UNSUPPORTED = "unsupported"
STATUS_UNDOCUMENTED = "not documented"

_LINUX_BY_VENDOR = {
    "nvidia": PLATFORM_LINUX_CUDA,
    "amd": PLATFORM_LINUX_ROCM,
    "intel": PLATFORM_LINUX_XPU,
}


@dataclass(frozen=True)
class EngineSupport:
    engine: str
    engine_version: str
    platform: str
    status: str
    scope: str | None
    quote: str | None
    url: str | None
    detail: str | None
    maintenance: str | None


@lru_cache(maxsize=1)
def load_engine_support() -> dict:
    return json.loads(
        files("chimeraforge.planner.data")
        .joinpath("engine_support.json")
        .read_text(encoding="utf-8")
    )


def platform_key(system: str, vendor: str | None, wsl: bool = False) -> str:
    """The matrix row for an OS + GPU vendor. No GPU (or an unknown vendor on
    Linux) is the CPU row; Windows is the native row whatever the vendor, since
    the engines document Windows per OS, not per card."""
    if system == "Windows":
        return PLATFORM_WINDOWS
    if system == "Linux":
        if wsl:
            return PLATFORM_WSL2
        return _LINUX_BY_VENDOR.get(vendor or "", PLATFORM_CPU)
    if system == "Darwin" and vendor == "apple":
        return PLATFORM_MACOS
    return PLATFORM_CPU


def engine_support(engine: str, platform: str) -> EngineSupport:
    """One cell. An engine or platform the matrix does not carry is reported as
    not documented rather than raising, so a new backend degrades to silence."""
    data = load_engine_support()
    row = data["engines"].get(engine)
    cell = (row or {}).get("platforms", {}).get(platform)
    if not row or not cell:
        return EngineSupport(
            engine, "", platform, STATUS_UNDOCUMENTED, None, None, None, None, None
        )
    maintenance = row.get("maintenance")
    if isinstance(maintenance, dict):
        maintenance = maintenance.get("quote") or maintenance.get("status")
    return EngineSupport(
        engine,
        row.get("version", ""),
        platform,
        cell["status"],
        cell.get("scope"),
        cell.get("quote"),
        cell.get("url"),
        cell.get("detail"),
        maintenance,
    )


def platform_support(platform: str) -> list[EngineSupport]:
    return [engine_support(e, platform) for e in load_engine_support()["engines"]]


def staleness_warning(today: dt.date | None = None) -> str | None:
    captured = dt.date.fromisoformat(load_engine_support()["captured_at"])
    age = ((today or dt.date.today()) - captured).days
    if age > MAX_AGE_DAYS:
        return (
            f"engine-support matrix captured {captured} ({age} days ago): engines "
            "release every few weeks, so re-run scripts/build_engine_support.py"
        )
    return None
