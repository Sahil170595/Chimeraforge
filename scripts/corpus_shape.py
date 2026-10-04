"""Render the README's statement of what the planner's bundled tables hold.

"~204,000 real measurements" is true of the research program and reads as if it
backs the planner's throughput table, which is 23 FP16 rows from one GPU. The
README states the real shape next to the claim; this script computes it from the
bundled data so the statement cannot drift from what ships.

Usage
-----
    python scripts/corpus_shape.py --check   # README block == render
    python scripts/corpus_shape.py --write   # rewrite the README block

Every figure is recomputed from the lookups themselves. The ``coverage`` record in
``fitted_models.json`` ``_provenance`` is cross-checked against the recomputation
and the render fails if they disagree, so neither can quietly go stale.
"""

from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from chimeraforge.planner.constants import BACKENDS, MODEL_PARAMS_B  # noqa: E402
from chimeraforge.planner.evalstats import BUNDLED_EVAL_N, BUNDLED_EVAL_SOURCE  # noqa: E402

FITTED = ROOT / "src" / "chimeraforge" / "planner" / "data" / "fitted_models.json"
SCORECARD = ROOT / "corpora" / "scorecard.json"
CORPORA = ROOT / "corpora"
README = ROOT / "README.md"
START = "<!-- corpus-shape:start (scripts/corpus_shape.py --write; do not edit by hand) -->"
END = "<!-- corpus-shape:end -->"


class ShapeError(RuntimeError):
    """The bundled data and its own provenance record disagree."""


def _split(key: str) -> list[str]:
    return key.split("|")


def measure(fitted: dict, scorecard: dict, audit_gpus: int) -> dict:
    """Recompute the shape of every bundled table from its rows."""
    tput = fitted["throughput"]["lookup"]
    rows = [_split(k) for k in tput]
    models = sorted({r[0] for r in rows})
    by_backend = collections.Counter(r[1] for r in rows)
    quants = sorted({r[2] for r in rows})
    serving = {b: n for b, n in sorted(by_backend.items()) if b in BACKENDS}
    harness = sum(n for b, n in by_backend.items() if b not in BACKENDS)
    sized = {m: MODEL_PARAMS_B[m] for m in models if m in MODEL_PARAMS_B}
    largest = max(sized, key=sized.get)
    shape = {
        "throughput_rows": len(tput),
        "throughput_models": models,
        "throughput_backends": sorted(by_backend),
        "throughput_quants": quants,
        "quality_cells": len(fitted["quality"]["lookup"]),
        "safety_cells": len(fitted["safety"]["lookup"]),
        "latency_service_times": len(fitted["latency"]["service_times"]),
    }
    recorded = fitted["_provenance"]["coverage"]
    drift = {k: (recorded.get(k), v) for k, v in shape.items() if recorded.get(k) != v}
    if drift:
        raise ShapeError(f"fitted_models.json _provenance.coverage is stale: {drift}")
    return {
        **shape,
        "serving_rows": serving,
        "harness_rows": harness,
        "largest_model": largest,
        "largest_params_b": sized[largest],
        "quant_multipliers": len(fitted["throughput"]["quant_multipliers"]),
        "quality_n": int(fitted["quality"].get("default_n", BUNDLED_EVAL_N)),
        "reference_hardware": fitted["_provenance"]["reference_hardware"],
        "limitations": list(fitted["_provenance"]["limitations"]),
        "audit_cells": scorecard["counts"]["cells"],
        "audit_underspecified": scorecard["counts"]["underspecified"],
        "audit_gpus": audit_gpus,
    }


def render(shape: dict) -> str:
    serving = ", ".join(f"{b} {n}" for b, n in shape["serving_rows"].items())
    rig = shape["reference_hardware"].split(" -- ")[0]
    quants = "/".join(shape["throughput_quants"])
    lines = [
        START,
        "**What the planner itself reads.** The ~204,000 measurements are the research "
        "program's total across its reports. The tables `plan` looks numbers up in are "
        "far smaller:",
        "",
        "| Table | Size | Shape |",
        "|---|---|---|",
        f"| Decode throughput | {shape['throughput_rows']} rows | {quants} only; "
        f"{len(shape['throughput_models'])} models, the largest "
        f"{shape['largest_model']} at {shape['largest_params_b']}B; "
        f"{sum(shape['serving_rows'].values())} rows on serving engines ({serving}) and "
        f"{shape['harness_rows']} on transformers research harnesses; every row measured "
        f"on one GPU, the {rig} |",
        f"| Quantization speedups | {shape['quant_multipliers']} multipliers | applied to "
        "an FP16 row; a quantized throughput is never a measurement of that quant |",
        f"| Quality | {shape['quality_cells']} model x quant cells | "
        f"n={shape['quality_n']} items each ({BUNDLED_EVAL_SOURCE}) |",
        f"| Safety | {shape['safety_cells']} model x quant cells | refusal rate (TR134/TR142) |",
        f"| Latency service times | {shape['latency_service_times']} | model x backend |",
        f"| Third-party audit | {shape['audit_cells']} scored cells on "
        f"{shape['audit_gpus']} GPUs | published benchmarks "
        f"([scorecard](corpora/SCORECARD.md)); {shape['audit_underspecified']} more "
        "published but too underspecified to score |",
        "",
        "Anything outside those rows is `extrapolated` (scaled by memory bandwidth from "
        "the reference GPU), `derived` (exact arithmetic) or `estimated` (roofline), and "
        "every number in a plan says which. The data records its own limits:",
        "",
        *[f"- {limit}" for limit in shape["limitations"]],
        END,
    ]
    return "\n".join(lines)


def current() -> str:
    fitted = json.loads(FITTED.read_text(encoding="utf-8"))
    scorecard = json.loads(SCORECARD.read_text(encoding="utf-8"))
    audit_gpus = len(list(CORPORA.glob("*.matrix.json")))
    return render(measure(fitted, scorecard, audit_gpus))


def readme_block(text: str) -> str:
    if text.count(START) != 1 or text.count(END) != 1:
        raise ShapeError("README must carry exactly one corpus-shape block")
    return text[text.index(START) : text.index(END) + len(END)]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--check", action="store_true", help="fail if the README block differs")
    ap.add_argument("--write", action="store_true", help="rewrite the README block")
    args = ap.parse_args()
    if args.check == args.write:
        ap.error("pass exactly one of --check / --write")
    text = README.read_text(encoding="utf-8")
    block = current()
    if args.check:
        if readme_block(text) != block:
            print("README corpus-shape block is stale; run --write", file=sys.stderr)
            return 1
        print("README corpus-shape block matches the bundled data")
        return 0
    README.write_text(text.replace(readme_block(text), block), encoding="utf-8")
    print("wrote the README corpus-shape block")
    return 0


if __name__ == "__main__":
    sys.exit(main())
