"""Build and validate the per-platform serving-engine support matrix.

The planner has offered every engine on every GPU: vLLM on native Windows,
SGLang on a consumer Radeon, TGI on a Mac. Each engine's own install docs say
where it runs, so this dataset records that -- engine x platform -- with a
verbatim quote and a URL pinned to the release tag it was read at.

Usage
-----
    python scripts/build_engine_support.py --check    # bundled file == rebuild
    python scripts/build_engine_support.py --write    # regenerate it

Inputs
------
``scripts/engine_support_sources.json`` is the extraction record: every cell read
from the engine's own docs (or its source at the tag, where the docs were silent)
with the quote and a ``/blob/<tag>/`` URL. This script does not edit it. It adds
one reviewed, machine-readable field per cell -- ``scope`` -- below, so the
enforcement step can act on "Instinct only" without parsing prose, and it fails
loudly on any cell whose claim is not pinned to the engine's recorded tag.

Rules
-----
- A cell that claims anything (supported / experimental / unsupported) must carry
  a quote and a URL containing ``/blob/<tag>/`` for that engine's tag.
- ``not documented`` carries no claim and no quote: silence is recorded as
  silence, never as "supported" or "unsupported".
- Every planner backend has a row for every platform.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCES = ROOT / "scripts" / "engine_support_sources.json"
DATASET = ROOT / "src" / "chimeraforge" / "planner" / "data" / "engine_support.json"

SCHEMA_VERSION = 1

PLATFORMS = (
    "linux-cuda",
    "linux-rocm",
    "linux-xpu",
    "windows-native",
    "windows-wsl2",
    "macos-apple-silicon",
    "cpu",
)
# The planner's backends (planner.constants.BACKENDS); every one needs a row.
ENGINES = ("ollama", "vllm", "tgi", "sglang")

STATUS_SUPPORTED = "supported"
STATUS_EXPERIMENTAL = "experimental"
STATUS_UNSUPPORTED = "unsupported"
STATUS_UNDOCUMENTED = "not documented"
CLAIMS = {STATUS_SUPPORTED, STATUS_EXPERIMENTAL, STATUS_UNSUPPORTED}
STATUSES = CLAIMS | {STATUS_UNDOCUMENTED}

# Reviewed scope per cell, each read off the quote in the extraction record. A
# cell absent here has no restriction beyond its status. The values are a closed
# vocabulary so PR 3's enforcement can match on them.
SCOPE = {
    ("vllm", "linux-xpu"): "basic",  # "initially supports basic model inference"
    ("vllm", "macos-apple-silicon"): "cpu-only",  # Metal only via a community plugin
    ("sglang", "linux-rocm"): "instinct-only",  # MI300X/MI325X/MI350X; no Radeon listed
    ("sglang", "linux-xpu"): "arc-b-series",  # "optimized for Intel Arc Pro B-Series"
    ("sglang", "macos-apple-silicon"): "mlx",  # the MLX runtime, macOS 14+
    ("sglang", "cpu"): "xeon-amx-only",  # 4th-gen+ Xeon Scalable with AMX
    ("tgi", "linux-cuda"): "full-on-h100-a100-a10g-t4",  # other GPUs lose flash/paged attn
    ("tgi", "linux-rocm"): "instinct-only",  # MI210, MI250, MI300
    ("tgi", "linux-xpu"): "max-only",  # Data Center GPU Max1100 / Max1550
    ("tgi", "cpu"): "intel-only",  # IPEX image; "not the intended platform"
    ("ollama", "linux-xpu"): "vulkan-only",  # Intel reached through Vulkan
    ("ollama", "windows-wsl2"): "docker-nvidia-only",  # nvidia-container-toolkit route
}
SCOPES = set(SCOPE.values())


class EngineSupportError(Exception):
    """The extraction record or the built dataset failed validation."""


def _tag(version: str) -> str:
    """'v0.30.0 (released 2026-09-22)' -> 'v0.30.0'."""
    return version.split()[0]


def build() -> dict:
    raw = json.loads(SOURCES.read_text(encoding="utf-8"))
    try:
        dt.date.fromisoformat(raw["captured_at"])
    except (KeyError, TypeError, ValueError) as exc:
        raise EngineSupportError("extraction record needs an ISO captured_at") from exc

    engines_out: dict[str, dict] = {}
    for engine in ENGINES:
        src = (raw.get("engines") or {}).get(engine)
        if not src:
            raise EngineSupportError(f"no extraction for planner backend {engine!r}")
        tag = _tag(src["version"])
        platforms_out = {}
        for platform in PLATFORMS:
            cell = (src.get("platforms") or {}).get(platform) or {}
            status = cell.get("status")
            where = f"{engine}/{platform}"
            if status not in STATUSES:
                raise EngineSupportError(f"{where}: status {status!r} not in {sorted(STATUSES)}")
            quote, url = cell.get("quote"), cell.get("url")
            if status in CLAIMS:
                if not quote or not url:
                    raise EngineSupportError(f"{where}: '{status}' needs a quote and a URL")
                if f"/blob/{tag}/" not in url:
                    raise EngineSupportError(f"{where}: URL is not pinned to {tag}: {url}")
            elif quote or url:
                raise EngineSupportError(f"{where}: 'not documented' must carry no claim")
            scope = SCOPE.get((engine, platform))
            if scope and status not in CLAIMS:
                raise EngineSupportError(f"{where}: a scope on an undocumented cell")
            platforms_out[platform] = {
                "status": status,
                "scope": scope,
                "quote": quote,
                "url": url,
                "detail": cell.get("detail"),
            }
        engines_out[engine] = {
            "version": tag,
            "maintenance": src.get("maintenance"),
            "quantization": src.get("quantization"),
            "platforms": platforms_out,
        }
    unused = set(SCOPE) - {(e, p) for e in ENGINES for p in PLATFORMS}
    if unused:
        raise EngineSupportError(f"scope set for cells that do not exist: {sorted(unused)}")
    return {
        "schema_version": SCHEMA_VERSION,
        "captured_at": raw["captured_at"],
        "note": (
            "Serving-engine support per platform, read from each engine's own docs "
            "(or its source at the release tag where the docs were silent). Every "
            "claim carries a verbatim quote and a URL pinned to that tag. 'not "
            "documented' is silence, not a verdict. `scope` narrows a claim (e.g. "
            "instinct-only). Regenerate with scripts/build_engine_support.py."
        ),
        "platforms": list(PLATFORMS),
        "engines": engines_out,
    }


def _text(data: dict) -> str:
    return json.dumps(data, indent=2, ensure_ascii=True) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--check", action="store_true", help="fail if the bundled file differs")
    ap.add_argument("--write", action="store_true", help="regenerate the bundled file")
    args = ap.parse_args()
    try:
        data = build()
    except EngineSupportError as exc:
        print(f"engine support invalid: {exc}", file=sys.stderr)
        return 1
    text = _text(data)
    if args.write:
        DATASET.write_text(text, encoding="utf-8")
        print(f"wrote {DATASET} ({len(ENGINES)} engines x {len(PLATFORMS)} platforms)")
        return 0
    if not DATASET.exists() or DATASET.read_text(encoding="utf-8") != text:
        print(f"{DATASET.name} is stale; run --write", file=sys.stderr)
        return 1
    print(
        f"OK: {len(ENGINES)} engines x {len(PLATFORMS)} platforms, captured {data['captured_at']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
