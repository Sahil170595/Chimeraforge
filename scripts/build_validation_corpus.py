"""Build, validate and audit the third-party validation corpus (P8.5).

`chimeraforge validate` shipped in 0.22.0 and had never been run against a real
measurement. This script turns published third-party benchmarks into
pre-registered, per-hardware audit matrices, then runs the audit exactly as a
user would, offline, against the bundled planner corpus.

Usage
-----
    python scripts/build_validation_corpus.py --check    # corpus on disk == rebuild
    python scripts/build_validation_corpus.py --write    # regenerate corpora/*.json
    python scripts/build_validation_corpus.py --audit    # run the audit, write the scorecard

Inputs
------
``scripts/validation_sources.json`` is the extraction record: every source
consulted (including those that yielded nothing, and why), and every cell read
from them with its verbatim quote, URL, capture date and serving config. It was
assembled by enumerating sources BEFORE extracting values. This script never
edits it; it applies the inclusion rules below and records every exclusion.

Inclusion rules
---------------
Fixed before any error was computed, and applied by code rather than by hand so
that nothing can be dropped after seeing how it scores:

1. Single GPU only. The audit predicts at tensor-parallel 1.
2. Batch 1 only. The audit predicts a single stream.
3. A stated metric definition. ``ambiguous`` cells are published as excluded.
4. The GPU variant must be the one the planner's entry describes. Its H100 80GB
   and A100 80GB entries carry SXM bandwidth, so PCIe cells are excluded, not
   silently scored against a 40-70% higher bandwidth than the card had.
5. llama.cpp on CUDA or ROCm maps to the planner's GGUF backend (what Ollama
   ships). Vulkan is a different kernel path the planner does not model.
6. Default engine configuration only (e.g. SGLang without torch.compile).
7. Two sources measuring the same cell: keep the fully specified one, then the
   most recent; the other is published as a superseded duplicate.

Evidence limits, stated rather than hidden: llama-bench measures llama.cpp
directly, not through Ollama's HTTP layer; decode rates are measured with no
prompt in context; and several sources omit their engine build, which makes
those cells ``underspecified`` -- published, but kept out of the headline.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import hashlib
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from chimeraforge.validate import (  # noqa: E402
    DEF_AMBIGUOUS,
    DEF_PREFILL,
    EVIDENCE_THIRD_PARTY,
    Audit,
    Matrix,
    MeasuredCell,
    MatrixCell,
    audit_cells,
    format_markdown,
    load_measurements,
    models_file,
    score,
)

SOURCES_FILE = ROOT / "scripts" / "validation_sources.json"
HARDWARE_FILE = ROOT / "src" / "chimeraforge" / "planner" / "data" / "hardware.json"
CORPUS_DIR = ROOT / "corpora"
AUDIT_DIR = CORPUS_DIR / "audits"

# The date these matrices were registered. Committed before --audit first ran;
# the git history of corpora/*.matrix.json is the record of that order.
REGISTERED_AT = "2026-09-25"
# The date the published audit was run. Fixed, not today(), so --check does not
# drift daily; bump it when the audit is deliberately re-run.
AUDITED_AT = "2026-09-25"

# In-band tolerance per metric, registered with the matrices. The corpus's own
# spread sets the floor: one author's H100 SXM5 decode moved +13% between two
# llama.cpp builds, and flash attention moves decode 0-10%, so a band tighter
# than ~20% would fail a perfect model. TTFT gets a wider band because prefill
# is compute-bound and the planner's MFU is a single constant.
BANDS = {"throughput_tps": 0.25, "ttft_ms": 0.50, "e2e_latency_ms": 0.25}

# Architectures, from each model's config.json. Meta's repos are gated (401 on
# config.json), so the config is read from an ungated mirror; the mirror is
# checked by its safetensors parameter total matching Meta's own API figure to
# the parameter (captured 2026-09-25).
ARCH = {
    "llama-2-7b": {
        "params_b": 6.738417664,
        "n_layers": 32,
        "n_kv_heads": 32,
        "d_head": 128,
        "hidden_size": 4096,
        "config_url": "https://huggingface.co/NousResearch/Llama-2-7b-hf/blob/main/config.json",
        "params_url": "https://huggingface.co/api/models/meta-llama/Llama-2-7b-hf?expand[]=safetensors",
    },
    "llama-3-8b": {
        "params_b": 8.030261248,
        "n_layers": 32,
        "n_kv_heads": 8,
        "d_head": 128,
        "hidden_size": 4096,
        "config_url": "https://huggingface.co/NousResearch/Meta-Llama-3-8B/blob/main/config.json",
        "params_url": "https://huggingface.co/api/models/meta-llama/Meta-Llama-3-8B?expand[]=safetensors",
    },
    "llama-3-70b": {
        "params_b": 70.553706496,
        "n_layers": 80,
        "n_kv_heads": 8,
        "d_head": 128,
        "hidden_size": 8192,
        "config_url": "https://huggingface.co/NousResearch/Meta-Llama-3-70B/blob/main/config.json",
        "params_url": "https://huggingface.co/api/models/meta-llama/Meta-Llama-3-70B?expand[]=safetensors",
    },
    "mistral-7b-v0.1": {
        "params_b": 7.241732096,
        "n_layers": 32,
        "n_kv_heads": 8,
        "d_head": 128,
        "hidden_size": 4096,
        "config_url": "https://huggingface.co/mistralai/Mistral-7B-v0.1/blob/main/config.json",
        "params_url": "https://huggingface.co/api/models/mistralai/Mistral-7B-v0.1?expand[]=safetensors",
    },
}
SPEC_KEYS = ("params_b", "n_layers", "n_kv_heads", "d_head", "hidden_size")

# Cell shape for llama-bench style sources, which run prefill and decode as
# separate tests: the cell is the prefill prompt plus the decode length.
# Other sources state both lengths per measurement.
BENCH_SHAPE = {"S1": (512, 128), "S2": (512, 128), "S3": (512, 128), "S4": (512, 512)}

# Planner entries whose figures describe the SXM part (rule 4).
SXM_ENTRIES = {"H100 80GB", "A100 80GB"}
VULKAN_SOURCES = {"S3"}
NON_DEFAULT_FLAGS = ("--enable-torch-compile",)

# Memory technology per the vendor pages hardware.json already cites (A100
# HBM2e, H100 HBM3, H200/B200 HBM3e, MI300X HBM3); every other audited part is
# GDDR. The combined headline averages two populations whose errors have
# opposite signs, so the scorecard also reports each on its own.
HBM_PARTS = frozenset(
    {"A100 40GB", "A100 80GB", "H100 80GB", "H200 141GB", "B200 180GB", "MI300X 192GB"}
)


class CorpusError(Exception):
    """The extraction record or the built corpus failed validation."""


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _hardware() -> dict[str, dict]:
    return {g["name"]: g for g in json.loads(HARDWARE_FILE.read_text(encoding="utf-8"))["gpus"]}


def _exclusion(cell: dict, gpus: dict[str, dict]) -> str | None:
    """The first inclusion rule a raw cell fails, or None."""
    if cell["gpu_count"] != 1:
        return f"rule 1: {cell['gpu_count']} GPUs; the audit predicts tensor-parallel 1"
    # Checked before batch: an ambiguous source usually states no batch either,
    # and "which quantity is this" is the more fundamental failure.
    if cell["metric_definition"] == DEF_AMBIGUOUS:
        return "rule 3: the source does not state which quantity its figure is"
    if cell["batch"] != 1:
        return f"rule 2: batch {cell['batch']}; the audit predicts a single stream"
    if cell["planner_gpu"] in SXM_ENTRIES and "pcie" in cell["gpu"].lower():
        bw = gpus[cell["planner_gpu"]]["bandwidth_gbps"]
        return (
            f"rule 4: PCIe part, but the planner's {cell['planner_gpu']} entry is the SXM "
            f"part at {bw:.0f} GB/s"
        )
    if cell["source_id"][:2] in VULKAN_SOURCES:
        return "rule 5: Vulkan backend; the planner's GGUF path is CUDA/ROCm llama.cpp"
    if any(flag in cell["serving_config"] for flag in NON_DEFAULT_FLAGS):
        return "rule 6: non-default engine configuration"
    if not cell["mapping"].get("model_key"):
        return "no planner identity for this model/quant"
    return None


def _shape(cell: dict) -> tuple[int, int]:
    fixed = BENCH_SHAPE.get(cell["source_id"][:2])
    if fixed:
        return fixed
    return int(cell["prompt_tokens"]), int(cell["output_tokens"])


def _record(group: list[dict]) -> dict:
    """One matrix cell's sourced measurement, from the raw cells of one source run."""
    first = group[0]
    metrics = []
    for c in group:
        m = {
            "definition": c["metric_definition"],
            "value": c["value"],
            "quote": c["verbatim_quote"],
        }
        if c["metric_definition"] == DEF_PREFILL:
            m["prompt_tokens"] = int(c["prompt_tokens"])
        metrics.append(m)
    defs = [m["definition"] for m in metrics]
    if len(set(defs)) != len(defs):
        raise CorpusError(
            f"one source run reports {defs} for one cell: {[c['cell_id'] for c in group]}"
        )
    return {
        "evidence": EVIDENCE_THIRD_PARTY,
        "source_url": first["source_url"],
        "captured_at": first["captured_at"],
        "underspecified": any(c["underspecified"] for c in group),
        "config_quote": " || ".join(sorted({c["serving_config"] for c in group})),
        "engine_version": (
            " || ".join(sorted({str(c["engine_version"]) for c in group if c["engine_version"]}))
            or None
        ),
        "notes": (
            f"{first['engine']}; GPU as stated: {first['gpu']}; model as stated: "
            f"{first['model']} ({first['as_stated_quant']}); raw cells "
            + ", ".join(c["cell_id"] for c in group)
        ),
        "metrics": metrics,
    }


def build() -> dict:
    """Apply the rules to the extraction record. Pure: returns every file's content."""
    raw = json.loads(SOURCES_FILE.read_text(encoding="utf-8"))
    gpus = _hardware()
    sources = raw["sources"]
    used = {s["id"]: s for s in sources if s["status"] == "used"}

    excluded: list[dict] = []
    groups: dict[tuple, list[dict]] = {}
    for c in raw["cells"]:
        for c_key in ("captured_at", "source_url", "metric_definition", "verbatim_quote"):
            if not c.get(c_key):
                raise CorpusError(f"{c.get('cell_id')}: missing {c_key}")
        if c["source_id"][:2] not in used:
            raise CorpusError(f"{c['cell_id']}: source {c['source_id']} is not a registered source")
        if c["planner_gpu"] not in gpus:
            raise CorpusError(f"{c['cell_id']}: {c['planner_gpu']!r} is not in hardware.json")
        why = _exclusion(c, gpus)
        if why:
            excluded.append({"cell_id": c["cell_id"], "source_url": c["source_url"], "reason": why})
            continue
        mp = c["mapping"]
        if mp["arch"] not in ARCH:
            raise CorpusError(f"{c['cell_id']}: no sourced architecture for {mp['arch']!r}")
        p, o = _shape(c)
        key = (c["planner_gpu"], mp["model_key"], mp["quant"], mp["backend"], mp["arch"], p, o)
        groups.setdefault((*key, c["source_url"]), []).append(c)

    # Every source run is validated by the loader's rules BEFORE rule 7 picks one,
    # so a bad record cannot hide inside a superseded duplicate.
    for group in groups.values():
        MeasuredCell.from_dict(group[0]["cell_id"], _record(group))

    # Rule 7: one measurement per matrix cell.
    by_cell: dict[tuple, list[list[dict]]] = {}
    for gkey, group in groups.items():
        by_cell.setdefault(gkey[:-1], []).append(group)

    matrices: dict[str, dict] = {}
    measured: dict[str, dict] = {}
    for key in sorted(by_cell):
        hardware, model_key, quant, backend, arch, p, o = key
        runs = sorted(
            by_cell[key],
            key=lambda g: (
                not any(c["underspecified"] for c in g),
                max(c["source_date"] for c in g),
            ),
            reverse=True,
        )
        kept, superseded = runs[0], runs[1:]
        for g in superseded:
            for c in g:
                excluded.append(
                    {
                        "cell_id": c["cell_id"],
                        "source_url": c["source_url"],
                        "reason": "rule 7: superseded duplicate of "
                        + ", ".join(k["cell_id"] for k in kept),
                    }
                )
        spec = {k: ARCH[arch][k] for k in SPEC_KEYS}
        cell = MatrixCell(
            model=model_key,
            quant=quant,
            backend=backend,
            prompt_tokens=p,
            avg_tokens=o,
            spec=tuple(sorted(spec.items())),
        )
        record = _record(kept)
        MeasuredCell.from_dict(cell.key, record)  # the loader's rules, at build time

        slug = _slug(hardware)
        mx = matrices.setdefault(
            slug,
            {
                "hardware": hardware,
                "registered_at": REGISTERED_AT,
                "notes": (
                    "Third-party validation matrix (P8.5), built by "
                    "scripts/build_validation_corpus.py from scripts/validation_sources.json. "
                    "Every consulted source is listed, including unused ones."
                ),
                "bands": BANDS,
                "sources": [
                    {k: s[k] for k in ("url", "status", "reason") if k in s} for s in sources
                ],
                "cells": [],
            },
        )
        mx["cells"].append(
            {
                "model": model_key,
                "quant": quant,
                "backend": backend,
                "prompt_tokens": p,
                "avg_tokens": o,
                "spec": spec,
            }
        )
        measured.setdefault(slug, {"schema_version": 2, "hardware": hardware, "cells": {}})[
            "cells"
        ][cell.key] = record

    for slug, mx in matrices.items():
        Matrix.from_dict(mx)  # fails loudly on anything the CLI would reject
    for s in used:
        if not any(c["source_id"][:2] == s for c in raw["cells"]):
            raise CorpusError(f"source {s} is marked used but contributed no cell")

    return {
        "matrices": matrices,
        "measured": measured,
        "exclusions": {
            "captured_at": raw["captured_at"],
            "rules": "see the docstring of scripts/build_validation_corpus.py",
            "excluded": sorted(excluded, key=lambda e: e["cell_id"]),
        },
        "architectures": ARCH,
    }


def _files(built: dict) -> dict[pathlib.Path, str]:
    out: dict[pathlib.Path, str] = {}
    for slug, mx in built["matrices"].items():
        out[CORPUS_DIR / f"{slug}.matrix.json"] = json.dumps(mx, indent=2) + "\n"
    for slug, ms in built["measured"].items():
        out[CORPUS_DIR / f"{slug}.measured.json"] = json.dumps(ms, indent=2) + "\n"
    out[CORPUS_DIR / "exclusions.json"] = json.dumps(built["exclusions"], indent=2) + "\n"
    out[CORPUS_DIR / "architectures.json"] = json.dumps(built["architectures"], indent=2) + "\n"
    return out


def run_audit() -> dict:
    """Run every matrix through the real audit path, offline, on the bundled corpus."""
    audits: list[Audit] = []
    for mx_path in sorted(CORPUS_DIR.glob("*.matrix.json")):
        matrix = Matrix.load(mx_path)
        measurements = load_measurements(
            mx_path.with_name(mx_path.name.replace("matrix", "measured"))
        )
        if measurements.hardware != matrix.hardware:
            raise CorpusError(f"{mx_path.name}: measurements are for {measurements.hardware}")
        with models_file(None) as models_path:
            outcomes = audit_cells(matrix, measurements, models_path)
        audit = Audit(
            fingerprint=matrix.fingerprint(),
            registered_at=matrix.registered_at,
            generated_at=AUDITED_AT,
            hardware=matrix.hardware,
            outcomes=outcomes,
            rows=score(outcomes, matrix.bands),
            notes=matrix.notes,
            bands=matrix.bands,
            sources=matrix.sources,
        )
        audits.append(audit)
    return {"audits": audits}


def combined(audits: list[Audit]) -> Audit:
    """All hardware in one scorecard; the fingerprint covers every matrix's."""
    # Cell keys are unique per GPU, not across GPUs; name the GPU in the joint view.
    outcomes = [
        dataclasses.replace(o, key=f"{a.hardware} :: {o.key}") for a in audits for o in a.outcomes
    ]
    joint = hashlib.sha256(
        "".join(sorted(a.fingerprint for a in audits)).encode("utf-8")
    ).hexdigest()
    return Audit(
        fingerprint=joint,
        registered_at=REGISTERED_AT,
        generated_at=AUDITED_AT,
        hardware=f"{len(audits)} GPUs (third-party published benchmarks)",
        outcomes=outcomes,
        rows=score(outcomes, BANDS),
        notes=(
            "Combined over every per-GPU matrix in corpora/. Each per-GPU audit, with "
            "its own fingerprint, is in corpora/audits/."
        ),
        bands=BANDS,
        sources=audits[0].sources if audits else [],
    )


def by_memory(audits: list[Audit]) -> dict[str, list]:
    """Headline rows recomputed separately for HBM and GDDR parts."""
    out = {}
    for label, members in (("HBM", True), ("GDDR", False)):
        outcomes = [o for a in audits if (a.hardware in HBM_PARTS) == members for o in a.outcomes]
        out[label] = score(outcomes, BANDS)
    return out


def scorecard_markdown(audit: Audit, audits: list[Audit]) -> str:
    """The combined report plus a table of every scored cell, worst first."""
    lines = [format_markdown(audit), "", "## By memory type", ""]
    lines += [
        "_The combined rows above average two populations whose errors have opposite "
        "signs. Fully specified cells only, as above._",
        "",
        "| Memory | Metric | n | In-band | Median abs | GMFE | Bias (median signed) |",
        "|---|---|---|---|---|---|---|",
    ]
    for label, rows in by_memory(audits).items():
        for r in rows:
            in_band = "n/a" if r.pass_rate is None else f"{r.pass_rate:.0%}"
            gmfe = "n/a" if r.gmfe is None else f"{r.gmfe:.2f}x"
            lines.append(
                f"| {label} | {r.metric} | {r.n} | {in_band} | {r.median_abs:.1%} | {gmfe} | "
                f"{r.median_signed:+.1%} |"
            )
    lines += ["", "## Every scored cell", ""]
    lines += [
        "| GPU | Cell | Class | Metric | Predicted | Measured (basis) | Error | Source |",
        "|---|---|---|---|---|---|---|---|",
    ]
    rows = []
    for a in audits:
        for o in a.outcomes:
            if o.skipped:
                continue
            for metric, err in o.errors.items():
                rows.append((a.hardware, o, metric, err))
    rows.sort(key=lambda r: -abs(r[3]))
    for hw, o, metric, err in rows:
        flag = " (underspecified)" if o.underspecified else ""
        url = o.measurement.source_url if o.measurement else ""
        lines.append(
            f"| {hw} | `{o.key.replace('|', chr(92) + '|')}`{flag} | {o.provenance_class} | "
            f"{metric} | {o.predicted[metric]:.1f} | {o.measured[metric]:.1f} "
            f"({o.measured_basis.get(metric, '')}) | {err:+.1%} | [link]({url}) |"
        )
    fps = "\n".join(f"- {a.hardware}: `{a.fingerprint}`" for a in audits)
    lines += ["", "## Matrix fingerprints", "", fps, ""]
    return "\n".join(lines)


def write_audit(result: dict) -> None:
    audits = result["audits"]
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    for a in audits:
        slug = _slug(a.hardware)
        (AUDIT_DIR / f"{slug}.audit.json").write_text(
            json.dumps(a.to_dict(), indent=2) + "\n", encoding="utf-8"
        )
    joint = combined(audits)
    (CORPUS_DIR / "scorecard.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generated_at": AUDITED_AT,
                "combined_fingerprint": joint.fingerprint,
                "matrix_fingerprints": {a.hardware: a.fingerprint for a in audits},
                "bands": BANDS,
                "scorecard": [r.to_dict() for r in joint.rows],
                "by_memory": {
                    label: [r.to_dict() for r in rows] for label, rows in by_memory(audits).items()
                },
                "counts": {
                    "cells": len(joint.outcomes),
                    "skipped": len(joint.skipped),
                    "underspecified": len(joint.underspecified),
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (CORPUS_DIR / "SCORECARD.md").write_text(
        scorecard_markdown(joint, audits) + "\n", encoding="utf-8"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--check", action="store_true", help="fail if corpora/ differs from a rebuild")
    ap.add_argument("--write", action="store_true", help="regenerate corpora/*.json")
    ap.add_argument("--audit", action="store_true", help="run the audit and write the scorecard")
    args = ap.parse_args()

    try:
        dt.date.fromisoformat(REGISTERED_AT)
        built = build()
    except CorpusError as exc:
        print(f"corpus invalid: {exc}", file=sys.stderr)
        return 1
    files = _files(built)

    if args.write:
        CORPUS_DIR.mkdir(parents=True, exist_ok=True)
        for path, text in files.items():
            path.write_text(text, encoding="utf-8")
        n_cells = sum(len(m["cells"]) for m in built["matrices"].values())
        print(
            f"wrote {len(built['matrices'])} matrices, {n_cells} cells, "
            f"{len(built['exclusions']['excluded'])} exclusions -> {CORPUS_DIR}"
        )
    if args.audit:
        write_audit(run_audit())
        print(f"audit -> {AUDIT_DIR}, {CORPUS_DIR / 'SCORECARD.md'}")
    if not args.write and not args.audit:
        drift = [
            str(p.relative_to(ROOT))
            for p, text in files.items()
            if not p.exists() or p.read_text(encoding="utf-8") != text
        ]
        if drift:
            print("corpora/ is stale; run --write:\n  " + "\n  ".join(drift), file=sys.stderr)
            return 1
        print(f"OK: {len(files)} corpus files match a rebuild")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
