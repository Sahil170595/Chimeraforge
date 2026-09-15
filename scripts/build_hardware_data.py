"""Regenerate and validate the bundled GPU specification dataset.

P8.6. `hardware.py` was a hand-typed dict of 22 `GPUSpec` literals with a prose
comment block for provenance -- no `captured_at`, no per-field source, no
regeneration path, and `$/hr` described in its own comment as "approximate". That
is the project's own house rule ("Regenerable, not hand-typed... A dataset
without a `captured_at` and a source is not shippable") unmet in the one dataset
that drives every throughput number, since decode is modelled as bandwidth-bound.

This mirrors `build_cost_data.py`: the values and their sources live here, the
bundled JSON is generated, and validation is strict and always runs.

Usage
-----
    python scripts/build_hardware_data.py --check    # validate the bundled file
    python scripts/build_hardware_data.py --write    # regenerate it

Two things this deliberately does NOT do.

It does not scrape. `techpowerup.com/gpu-specs/` returns HTTP 403 to automated
fetch, and vendor spec pages are JavaScript-rendered marketing pages whose layout
changes without notice. So the source URL is recorded per field and the value is
updated by a human reading that page, with `captured_at` bumped -- the point is
that every number traces to a page someone read on a known date, not that a
scrape always succeeds.

It does not invent a figure to fill a gap. Consumer memory bandwidth and dense
tensor TFLOPS are frequently absent from vendor pages. A field with no vendor
source is `null`, and a `null` field disables the prediction that depends on it
rather than defaulting -- unknown bandwidth means throughput is `unknown`, not
roofline-with-a-guess.

**Every value below is the value `hardware.py` already carried.** This item is a
migration plus a provenance record; a spec change would be a separate, arguable
thing, and mixing the two would hide it.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATASET = ROOT / "src" / "chimeraforge" / "planner" / "data" / "hardware.json"

SCHEMA_VERSION = 1

# How a `$/hr` figure was arrived at. The old field mixed two incompatible
# quantities under one name -- its own comment said datacenter values are
# "approximate on-demand cloud rates" and consumer values are "amortised card
# cost" -- and the field drives the budget gate, $/1M-tok, and the
# self-host-vs-API break-even, so the basis has to travel with it.
#
# The datacenter values also do not match the basis they claimed: H100 at
# $2.50/hr and B200 at $5.50/hr track GPU *marketplace* rates, roughly 4-5x
# below hyperscaler on-demand. They are relabelled to what they are rather than
# being changed, because changing them is a pricing decision and this is a
# migration.
BASIS_MARKETPLACE = "marketplace"
BASIS_HYPERSCALER = "hyperscaler-on-demand"
BASIS_AMORTISED = "amortised-purchase"
PRICE_BASES = {BASIS_MARKETPLACE, BASIS_HYPERSCALER, BASIS_AMORTISED}

# How a TFLOPS figure was derived, per the rule `hardware.py`'s comment block
# states. `dense` is a datasheet row. `halved-with-sparsity` is a datasheet that
# publishes only a sparse figure, divided by two -- defensible, but not a
# datasheet row, and NOT universally safe: AMD prints both columns for some parts
# and no sparsity figure at all for others, so halving an unlabeled headline
# would understate a dense number by 2x. `derived-2x-fp32` is the consumer rule.
TFLOPS_DENSE = "dense"
TFLOPS_HALVED = "halved-with-sparsity"
TFLOPS_2X_FP32 = "derived-2x-fp32"
TFLOPS_FP32_ACCUM = "fp32-accumulate-dense"
TFLOPS_BASES = {TFLOPS_DENSE, TFLOPS_HALVED, TFLOPS_2X_FP32, TFLOPS_FP32_ACCUM}

NVIDIA_GEFORCE = "https://www.nvidia.com/en-us/geforce/graphics-cards/"
NVIDIA_LAPTOPS = "https://www.nvidia.com/en-us/geforce/laptops/compare/"
NVIDIA_DC = "https://www.nvidia.com/en-us/data-center/"
AMD_MI300X = "https://www.amd.com/en/products/accelerators/instinct/mi300/mi300x.html"

# name, vram_gb, bandwidth, $/hr, price_basis, fp16_tflops, tflops_basis, tdp,
# interconnect, fp8, source_url, captured_at
#
# `captured_at` is the date the figure was last read from `source_url`. The
# reference card's specs were re-read on 2026-08-22 when 0.30.4 corrected them
# (see hardware.py's comment block); the rest carry the date this dataset was
# first assembled from the values that comment block documents.
_ASSEMBLED = "2026-09-05"
_REFERENCE_READ = "2026-08-22"

GPUS: list[dict] = [
    # -- Consumer, NVIDIA Ada (PCIe 4.0 = 64 GB/s) --------------------------
    dict(name="RTX 4060 8GB", vram_gb=8.0, bandwidth_gbps=272.0, cost_per_hour=0.020,
         price_basis=BASIS_AMORTISED, fp16_tflops=30.2, tflops_basis=TFLOPS_2X_FP32,
         tdp_watts=115.0, interconnect_gbps=64.0, fp8_supported=True,
         source_url=NVIDIA_GEFORCE, captured_at=_ASSEMBLED),
    dict(name="RTX 4060 Ti 8GB", vram_gb=8.0, bandwidth_gbps=288.0, cost_per_hour=0.025,
         price_basis=BASIS_AMORTISED, fp16_tflops=44.1, tflops_basis=TFLOPS_2X_FP32,
         tdp_watts=160.0, interconnect_gbps=64.0, fp8_supported=True,
         source_url=NVIDIA_GEFORCE, captured_at=_ASSEMBLED),
    dict(name="RTX 4060 Ti 16GB", vram_gb=16.0, bandwidth_gbps=288.0, cost_per_hour=0.030,
         price_basis=BASIS_AMORTISED, fp16_tflops=44.1, tflops_basis=TFLOPS_2X_FP32,
         tdp_watts=165.0, interconnect_gbps=64.0, fp8_supported=True,
         source_url=NVIDIA_GEFORCE, captured_at=_ASSEMBLED),
    dict(name="RTX 4070 12GB", vram_gb=12.0, bandwidth_gbps=504.0, cost_per_hour=0.030,
         price_basis=BASIS_AMORTISED, fp16_tflops=58.4, tflops_basis=TFLOPS_2X_FP32,
         tdp_watts=200.0, interconnect_gbps=64.0, fp8_supported=True,
         source_url=NVIDIA_GEFORCE, captured_at=_ASSEMBLED),
    dict(name="RTX 4070 Ti 12GB", vram_gb=12.0, bandwidth_gbps=504.0, cost_per_hour=0.035,
         price_basis=BASIS_AMORTISED, fp16_tflops=80.2, tflops_basis=TFLOPS_2X_FP32,
         tdp_watts=285.0, interconnect_gbps=64.0, fp8_supported=True,
         source_url=NVIDIA_GEFORCE, captured_at=_ASSEMBLED),
    # The reference rig: an RTX 4080 LAPTOP part, 12 GB GDDR6 on a 192-bit bus at
    # a 60-150 W TGP. Its bandwidth is the denominator of every cross-GPU
    # extrapolation and of MBU_DEFAULT, so it is the one entry whose figures were
    # re-read from the vendor page rather than inherited.
    dict(name="RTX 4080 12GB", vram_gb=12.0, bandwidth_gbps=432.0, cost_per_hour=0.035,
         price_basis=BASIS_AMORTISED, fp16_tflops=67.7, tflops_basis=TFLOPS_2X_FP32,
         tdp_watts=150.0, interconnect_gbps=64.0, fp8_supported=True,
         source_url=NVIDIA_LAPTOPS, captured_at=_REFERENCE_READ),
    dict(name="RTX 4080 16GB", vram_gb=16.0, bandwidth_gbps=717.0, cost_per_hour=0.045,
         price_basis=BASIS_AMORTISED, fp16_tflops=97.5, tflops_basis=TFLOPS_2X_FP32,
         tdp_watts=320.0, interconnect_gbps=64.0, fp8_supported=True,
         source_url=NVIDIA_GEFORCE, captured_at=_ASSEMBLED),
    dict(name="RTX 4090 24GB", vram_gb=24.0, bandwidth_gbps=1008.0, cost_per_hour=0.060,
         price_basis=BASIS_AMORTISED, fp16_tflops=165.2, tflops_basis=TFLOPS_2X_FP32,
         tdp_watts=450.0, interconnect_gbps=64.0, fp8_supported=True,
         source_url=NVIDIA_GEFORCE, captured_at=_ASSEMBLED),
    # -- Consumer, NVIDIA Blackwell (GDDR7, PCIe 5.0 = 128 GB/s) ------------
    dict(name="RTX 5070 12GB", vram_gb=12.0, bandwidth_gbps=672.0, cost_per_hour=0.030,
         price_basis=BASIS_AMORTISED, fp16_tflops=61.7, tflops_basis=TFLOPS_2X_FP32,
         tdp_watts=250.0, interconnect_gbps=128.0, fp8_supported=True,
         source_url=NVIDIA_GEFORCE, captured_at=_ASSEMBLED),
    dict(name="RTX 5070 Ti 16GB", vram_gb=16.0, bandwidth_gbps=896.0, cost_per_hour=0.038,
         price_basis=BASIS_AMORTISED, fp16_tflops=87.9, tflops_basis=TFLOPS_2X_FP32,
         tdp_watts=300.0, interconnect_gbps=128.0, fp8_supported=True,
         source_url=NVIDIA_GEFORCE, captured_at=_ASSEMBLED),
    dict(name="RTX 5080 16GB", vram_gb=16.0, bandwidth_gbps=960.0, cost_per_hour=0.045,
         price_basis=BASIS_AMORTISED, fp16_tflops=112.6, tflops_basis=TFLOPS_2X_FP32,
         tdp_watts=360.0, interconnect_gbps=128.0, fp8_supported=True,
         source_url=NVIDIA_GEFORCE, captured_at=_ASSEMBLED),
    dict(name="RTX 5090 32GB", vram_gb=32.0, bandwidth_gbps=1792.0, cost_per_hour=0.075,
         price_basis=BASIS_AMORTISED, fp16_tflops=209.5, tflops_basis=TFLOPS_2X_FP32,
         tdp_watts=575.0, interconnect_gbps=128.0, fp8_supported=True,
         source_url=NVIDIA_GEFORCE, captured_at=_ASSEMBLED),
    # -- Consumer, NVIDIA Ampere (no FP8 tensor cores) ---------------------
    dict(name="RTX 3090 24GB", vram_gb=24.0, bandwidth_gbps=936.0, cost_per_hour=0.040,
         price_basis=BASIS_AMORTISED, fp16_tflops=71.0, tflops_basis=TFLOPS_FP32_ACCUM,
         tdp_watts=350.0, interconnect_gbps=64.0, fp8_supported=False,
         source_url=NVIDIA_GEFORCE, captured_at=_ASSEMBLED),
    dict(name="RTX 3080 10GB", vram_gb=10.0, bandwidth_gbps=760.0, cost_per_hour=0.025,
         price_basis=BASIS_AMORTISED, fp16_tflops=59.5, tflops_basis=TFLOPS_FP32_ACCUM,
         tdp_watts=320.0, interconnect_gbps=64.0, fp8_supported=False,
         source_url=NVIDIA_GEFORCE, captured_at=_ASSEMBLED),
    # -- Data-center, NVIDIA (NVLink) --------------------------------------
    dict(name="A100 40GB", vram_gb=40.0, bandwidth_gbps=1555.0, cost_per_hour=1.10,
         price_basis=BASIS_MARKETPLACE, fp16_tflops=312.0, tflops_basis=TFLOPS_DENSE,
         tdp_watts=400.0, interconnect_gbps=600.0, fp8_supported=False,
         source_url=NVIDIA_DC + "a100/", captured_at=_ASSEMBLED),
    dict(name="A100 80GB", vram_gb=80.0, bandwidth_gbps=2039.0, cost_per_hour=1.60,
         price_basis=BASIS_MARKETPLACE, fp16_tflops=312.0, tflops_basis=TFLOPS_DENSE,
         tdp_watts=400.0, interconnect_gbps=600.0, fp8_supported=False,
         source_url=NVIDIA_DC + "a100/", captured_at=_ASSEMBLED),
    dict(name="H100 80GB", vram_gb=80.0, bandwidth_gbps=3352.0, cost_per_hour=2.50,
         price_basis=BASIS_MARKETPLACE, fp16_tflops=989.0, tflops_basis=TFLOPS_DENSE,
         tdp_watts=700.0, interconnect_gbps=900.0, fp8_supported=True,
         source_url=NVIDIA_DC + "h100/", captured_at=_ASSEMBLED),
    # H200 shares H100's GH100 compute die; only its memory differs.
    dict(name="H200 141GB", vram_gb=141.0, bandwidth_gbps=4800.0, cost_per_hour=3.50,
         price_basis=BASIS_MARKETPLACE, fp16_tflops=989.0, tflops_basis=TFLOPS_DENSE,
         tdp_watts=700.0, interconnect_gbps=900.0, fp8_supported=True,
         source_url=NVIDIA_DC + "h200/", captured_at=_ASSEMBLED),
    # HGX B200 per-GPU datasheet figures (180 GB / 7.7 TB/s), not the 192 GB
    # raw-stack number. The datasheet prints only a with-sparsity FP16 figure
    # (4500), so the dense value is that halved -- recorded as such.
    dict(name="B200 180GB", vram_gb=180.0, bandwidth_gbps=7700.0, cost_per_hour=5.50,
         price_basis=BASIS_MARKETPLACE, fp16_tflops=2250.0, tflops_basis=TFLOPS_HALVED,
         tdp_watts=1000.0, interconnect_gbps=1800.0, fp8_supported=True,
         source_url=NVIDIA_DC + "dgx-b200/", captured_at=_ASSEMBLED),
    dict(name="L4 24GB", vram_gb=24.0, bandwidth_gbps=300.0, cost_per_hour=0.50,
         price_basis=BASIS_MARKETPLACE, fp16_tflops=121.0, tflops_basis=TFLOPS_DENSE,
         tdp_watts=72.0, interconnect_gbps=64.0, fp8_supported=True,
         source_url=NVIDIA_DC + "l4/", captured_at=_ASSEMBLED),
    dict(name="T4 16GB", vram_gb=16.0, bandwidth_gbps=320.0, cost_per_hour=0.35,
         price_basis=BASIS_MARKETPLACE, fp16_tflops=65.0, tflops_basis=TFLOPS_DENSE,
         tdp_watts=70.0, interconnect_gbps=64.0, fp8_supported=False,
         source_url=NVIDIA_DC + "tesla-t4/", captured_at=_ASSEMBLED),
    # -- Data-center, AMD (Infinity Fabric) --------------------------------
    # MI300X's sheet prints the dense 1307 directly, so it is a datasheet row
    # rather than a halved sparse one.
    dict(name="MI300X 192GB", vram_gb=192.0, bandwidth_gbps=5300.0, cost_per_hour=2.00,
         price_basis=BASIS_MARKETPLACE, fp16_tflops=1307.0, tflops_basis=TFLOPS_DENSE,
         tdp_watts=750.0, interconnect_gbps=896.0, fp8_supported=True,
         source_url=AMD_MI300X, captured_at=_ASSEMBLED),
]

REQUIRED = (
    "name", "vram_gb", "bandwidth_gbps", "cost_per_hour", "price_basis",
    "fp16_tflops", "tflops_basis", "tdp_watts", "interconnect_gbps",
    "fp8_supported", "source_url", "captured_at",
)

# Sanity bounds. Anything outside these is far more likely to be a typo or a
# unit mix-up than a real part, so it fails the build rather than shipping.
BOUNDS = {
    "vram_gb": (1.0, 1024.0),
    "bandwidth_gbps": (10.0, 50000.0),
    "cost_per_hour": (0.001, 100.0),
    "fp16_tflops": (1.0, 100000.0),
    "tdp_watts": (5.0, 3000.0),
    "interconnect_gbps": (1.0, 10000.0),
}


class ValidationError(Exception):
    """The dataset does not satisfy the schema or its sanity bounds."""


def _iso(value: str, where: str) -> None:
    try:
        dt.date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{where}: captured_at {value!r} is not an ISO date") from exc


def validate(data: dict) -> list[str]:
    """Raise on anything unshippable; return non-fatal notes."""
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ValidationError(f"unsupported schema_version: {data.get('schema_version')!r}")
    _iso(data.get("captured_at", ""), "top level")
    gpus = data.get("gpus")
    if not isinstance(gpus, list) or not gpus:
        raise ValidationError("no gpus in dataset")

    notes: list[str] = []
    seen: set[str] = set()
    for entry in gpus:
        name = entry.get("name", "<unnamed>")
        for key in REQUIRED:
            if key not in entry:
                raise ValidationError(f"{name}: missing {key!r}")
        if name in seen:
            raise ValidationError(f"duplicate GPU name {name!r}")
        seen.add(name)
        if not str(entry["source_url"]).startswith("https://"):
            raise ValidationError(f"{name}: source_url must be https")
        _iso(entry["captured_at"], name)
        if entry["price_basis"] not in PRICE_BASES:
            raise ValidationError(
                f"{name}: price_basis {entry['price_basis']!r} not one of {sorted(PRICE_BASES)}"
            )
        if entry["tflops_basis"] not in TFLOPS_BASES:
            raise ValidationError(
                f"{name}: tflops_basis {entry['tflops_basis']!r} not one of {sorted(TFLOPS_BASES)}"
            )
        for field, (lo, hi) in BOUNDS.items():
            value = entry[field]
            if value is None:
                # A null is legal and means "no vendor source". It disables the
                # prediction that depends on it rather than defaulting.
                notes.append(f"{name}: {field} is null -- dependent predictions are unknown")
                continue
            if not isinstance(value, (int, float)):
                raise ValidationError(f"{name}: {field} is not a number")
            if not lo <= value <= hi:
                raise ValidationError(f"{name}: {field}={value} outside [{lo}, {hi}]")
        if not isinstance(entry["fp8_supported"], bool):
            raise ValidationError(f"{name}: fp8_supported must be a bool")
    return notes


def build() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "captured_at": max(g["captured_at"] for g in GPUS),
        "note": (
            "GPU specifications with per-entry source and capture date. Values are "
            "vendor-published figures; `tflops_basis` records which column each "
            "TFLOPS number came from, since a with-sparsity headline halved is not "
            "a datasheet row. `price_basis` distinguishes an amortised purchase "
            "price from a rental rate -- the two are not the same quantity, and "
            "the field drives the budget gate and the self-host-vs-API break-even. "
            "A null field means no vendor source; it disables the prediction that "
            "depends on it rather than defaulting. Regenerate with "
            "scripts/build_hardware_data.py."
        ),
        "gpus": GPUS,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="validate the bundled dataset")
    ap.add_argument("--write", action="store_true", help="regenerate the bundled dataset")
    args = ap.parse_args()

    if args.write:
        data = build()
        validate(data)
        DATASET.parent.mkdir(parents=True, exist_ok=True)
        DATASET.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {DATASET} ({len(data['gpus'])} GPUs)")
        return 0

    if not DATASET.exists():
        print(f"dataset missing: {DATASET}", file=sys.stderr)
        return 1
    data = json.loads(DATASET.read_text(encoding="utf-8"))
    notes = validate(data)
    for note in notes:
        print(f"  note: {note}")
    print(f"OK: {len(data['gpus'])} GPUs, captured {data['captured_at']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
