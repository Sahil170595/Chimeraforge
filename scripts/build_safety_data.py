#!/usr/bin/env python3
"""Build the ``safety`` block of fitted_models.json from TR134/TR142 research CSVs.

Reads refusal-rate (TR134) and RTSI behavioral-screen (TR142) data exported from
the Banterhearts TR142 analysis and vendored under ``data/safety/tr142/``, then
writes a ``safety`` block into the bundled ``fitted_models.json`` consumed by the
planner's Gate 5 (safety).

Lookup-only by design: TR142/TR146 show safety does not generalize across
(model, quant) cells, so no value is extrapolated. Only the GGUF quant levels the
planner can actually search are emitted; AWQ/GPTQ rows are dropped because the
planner has no throughput/VRAM data for them.

Run:
    python scripts/build_safety_data.py
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SAFETY_CSV = REPO / "data" / "safety" / "tr142" / "safety_wide.csv"
RTSI_CSV = REPO / "data" / "safety" / "tr142" / "rtsi_table.csv"
FITTED = REPO / "src" / "chimeraforge" / "planner" / "data" / "fitted_models.json"

# GGUF quant levels the planner searches (mirrors planner.constants.QUANT_LEVELS).
GGUF_QUANTS = {"FP16", "Q8_0", "Q6_K", "Q5_K_M", "Q4_K_M", "Q3_K_S", "Q2_K"}

ROUND = 4


def build_lookup_and_baselines() -> tuple[dict[str, float], dict[str, float]]:
    """Per-(model|quant) refusal rate, plus per-model FP16 baseline."""
    lookup: dict[str, float] = {}
    fp16_baselines: dict[str, float] = {}
    with SAFETY_CSV.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            quant = row["quant"]
            if quant not in GGUF_QUANTS:
                continue
            model = row["base_model"]
            refusal = round(float(row["safety_refusal_rate"]), ROUND)
            lookup[f"{model}|{quant}"] = refusal
            if quant == "FP16":
                fp16_baselines[model] = refusal
    return lookup, fp16_baselines


def build_rtsi() -> dict[str, dict]:
    """Per-(model|quant) RTSI score + risk tier (HIGH/MODERATE/LOW)."""
    rtsi: dict[str, dict] = {}
    with RTSI_CSV.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            quant = row["quant"]
            if quant not in GGUF_QUANTS:
                continue
            model = row["base_model"]
            rtsi[f"{model}|{quant}"] = {
                "score": round(float(row["rtsi_score"]), ROUND),
                "risk": row["rtsi_risk"],
            }
    return rtsi


def main() -> None:
    lookup, fp16_baselines = build_lookup_and_baselines()
    rtsi = build_rtsi()

    safety_block = {
        "lookup": dict(sorted(lookup.items())),
        "fp16_baselines": dict(sorted(fp16_baselines.items())),
        "rtsi": dict(sorted(rtsi.items())),
        "metric": "refusal_rate",
        "source": "TR134/TR142 (banterhearts research/tr142 phase56_v3_full_canonical)",
        "fitted": True,
    }

    data = json.loads(FITTED.read_text(encoding="utf-8"))
    data["safety"] = safety_block
    FITTED.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    n_high = sum(1 for v in rtsi.values() if v["risk"] == "HIGH")
    print(f"safety.lookup:         {len(lookup)} (model|quant) cells")
    print(f"safety.fp16_baselines: {len(fp16_baselines)} models")
    print(f"safety.rtsi:           {len(rtsi)} cells ({n_high} HIGH-risk)")
    print(f"wrote -> {FITTED}")


if __name__ == "__main__":
    main()
