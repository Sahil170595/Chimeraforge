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


# Operating systems a plan can target. A plan describes a deployment, not this
# machine, so the OS is an input; Linux is the default because the matrix's GPU
# rows are Linux rows, and the plan states which it assumed.
PLAN_PLATFORM_LINUX = "linux"
PLAN_PLATFORMS = ("linux", "windows", "wsl2", "macos")
DEFAULT_PLAN_PLATFORM = PLAN_PLATFORM_LINUX

# What each scope requires of the GPU, where it restricts GPUs at all. Scopes not
# listed narrow features, not hardware, and are reported as notes.
_SCOPE_REQUIRES = {
    "instinct-only": ("amd", "instinct"),
    "max-only": ("intel", "datacenter-max"),
    "arc-b-series": ("intel", "arc-pro"),
    "docker-nvidia-only": ("nvidia", None),
}
_SCOPE_NOTE = {
    "basic": "basic inference only, per its docs",
    "mlx": "through the MLX runtime",
    "vulkan-only": "through Vulkan",
    "full-on-h100-a100-a10g-t4": (
        "full features (flash/paged attention) only on H100/A100/A10G/T4, per its docs"
    ),
}


def local_plan_platform() -> str:
    """This machine's OS as a plan platform -- the default when the plan targets
    this machine (`--hardware auto`)."""
    import os
    import platform as _platform

    from chimeraforge.doctor import _read_text, detect_wsl

    system = _platform.system()
    if system == "Windows":
        return "windows"
    if system == "Darwin":
        return "macos"
    if system == "Linux" and detect_wsl(dict(os.environ), _read_text):
        return "wsl2"
    return PLAN_PLATFORM_LINUX


class PlatformError(ValueError):
    """A plan platform that cannot describe the requested hardware."""


def plan_platform_key(plan_platform: str, vendor: str) -> str | None:
    """The matrix row for a planned deployment, or None when the GPU vendor is
    unknown (a user-supplied card) and no row can be chosen honestly."""
    if plan_platform not in PLAN_PLATFORMS:
        raise PlatformError(
            f"unknown platform {plan_platform!r}; use one of: {', '.join(PLAN_PLATFORMS)}"
        )
    if vendor == "apple" and plan_platform != "macos":
        raise PlatformError(
            f"--platform {plan_platform} with Apple Silicon: no engine documents a "
            "non-macOS route for it; use --platform macos"
        )
    if plan_platform == "windows":
        return PLATFORM_WINDOWS
    if plan_platform == "wsl2":
        return PLATFORM_WSL2
    if plan_platform == "macos":
        if vendor and vendor != "apple":
            raise PlatformError(
                f"--platform macos with a {vendor} GPU: a Mac GPU is Apple Silicon, and "
                "unified-memory devices cannot be planned yet"
            )
        return PLATFORM_MACOS
    return _LINUX_BY_VENDOR.get(vendor) if vendor else None


@dataclass(frozen=True)
class EngineVerdict:
    """Whether a plan may offer this engine here, and what it must say if so."""

    allowed: bool
    reason: str | None = None  # the rejection, with its source
    warnings: tuple[str, ...] = ()


def check_engine(
    engine: str, platform: str | None, vendor: str, product_line: str, quant: str
) -> EngineVerdict:
    """Apply the engine's own documentation to one (engine, platform, GPU, quant).

    Refuses only on a documented statement: `unsupported`, a scope the GPU does
    not meet, or a quant the docs say the engine cannot serve there. Silence and
    `experimental` are warnings -- the docs not mentioning a platform is not
    evidence it fails -- and so is an unknown GPU vendor, since no row applies.
    """
    if platform is None:
        return EngineVerdict(
            True,
            warnings=(
                "GPU vendor unknown (a user-supplied card), so engine support for this "
                "platform was not checked against the engines' docs",
            ),
        )
    s = engine_support(engine, platform)
    cell = load_engine_support()["engines"].get(engine, {}).get("platforms", {}).get(platform, {})
    tag = f"{engine} {s.engine_version}".strip()
    if s.status == STATUS_UNSUPPORTED:
        return EngineVerdict(False, f'{tag} does not support {platform}: "{s.quote}" ({s.url})')
    need = _SCOPE_REQUIRES.get(s.scope or "")
    if need:
        need_vendor, need_line = need
        if vendor != need_vendor or (need_line and product_line != need_line):
            return EngineVerdict(
                False,
                f"{tag} on {platform} is documented for {s.scope} hardware only, not a "
                f"{vendor} {product_line} GPU ({s.url})",
            )
    if s.scope == "cpu-only":
        return EngineVerdict(
            False, f"{tag} on {platform} runs on the CPU only, not the GPU ({s.url})"
        )
    if quant in (cell.get("unsupported_quants") or []):
        return EngineVerdict(
            False,
            f"{tag} does not serve {quant} on {platform}, per its docs "
            f"({cell.get('unsupported_quants_url')})",
        )

    warnings = []
    if s.status == STATUS_UNDOCUMENTED:
        warnings.append(
            f"{tag} does not document {platform} support; this configuration is unverified"
        )
    elif s.status == STATUS_EXPERIMENTAL:
        warnings.append(f"{tag} support for {platform} is experimental, per its docs ({s.url})")
    if s.scope in _SCOPE_NOTE:
        warnings.append(f"{tag} on {platform}: {_SCOPE_NOTE[s.scope]} ({s.url})")
    if quant in (cell.get("quant_conflicts") or []):
        warnings.append(
            f"{tag}'s own docs disagree on {quant} for {platform}; unverified "
            f"({cell.get('quant_conflicts_url')})"
        )
    if s.maintenance:
        warnings.append(f"{tag}: {s.maintenance}")
    return EngineVerdict(True, warnings=tuple(warnings))


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
