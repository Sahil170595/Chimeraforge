#!/usr/bin/env python3
"""
TR121: Decode-length sweep runner.

Runs multiple TR121 scaling runs for different gen_tokens values (8/32/64/128 by default)
on a fixed subset of models/backends/scenarios, then analyzes each run.

Outputs:
  scripts/tr121/results/tr121_decode_sweep/<RUN_ID>/
    gen_8/<subrun>/
    gen_32/<subrun>/
    ...
  plus a combined CSV in:
    scripts/tr121/results/tr121_decode_sweep/<RUN_ID>/decode_sweep_summary.csv
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import subprocess
import time
from typing import Any

import pandas as pd
import yaml

try:  # Optional
    import matplotlib.pyplot as plt  # type: ignore
except Exception:  # pragma: no cover
    plt = None  # type: ignore


def _now_run_id() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for k in row.keys():
            if k not in fieldnames:
                fieldnames.append(k)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def _decode_fraction_tables(*, run_dir: Path, gen_tokens_target: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    agg = pd.read_csv(run_dir / "analysis" / "summary_by_model_backend_mode_agg.csv")

    kv = agg[agg["mode"] == "kv_decode"][
        ["backend", "backend_kind", "batch_size", "model", "model_kind", "latency_geomean_ms"]
    ].rename(columns={"latency_geomean_ms": "kv_decode_latency_ms"})

    e2e = agg[agg["mode"] == "e2e_kv"][
        ["backend", "backend_kind", "batch_size", "model", "model_kind", "latency_geomean_ms"]
    ].rename(columns={"latency_geomean_ms": "e2e_kv_latency_ms"})

    merged = kv.merge(
        e2e,
        on=["backend", "backend_kind", "batch_size", "model", "model_kind"],
        how="inner",
        validate="one_to_one",
    )
    merged["gen_tokens_target"] = int(gen_tokens_target)
    merged["decode_fraction"] = merged["kv_decode_latency_ms"] / merged["e2e_kv_latency_ms"]

    summary = (
        merged.groupby(["backend", "backend_kind", "gen_tokens_target"], dropna=False)
        .agg(
            n_models=("decode_fraction", "count"),
            decode_fraction_median=("decode_fraction", "median"),
            decode_fraction_p25=("decode_fraction", lambda s: float(s.quantile(0.25))),
            decode_fraction_p75=("decode_fraction", lambda s: float(s.quantile(0.75))),
        )
        .reset_index()
    )
    return merged, summary


def main() -> int:
    ap = argparse.ArgumentParser(description="TR121 decode-length sweep")
    ap.add_argument("--config", default="scripts/tr121/configs/decode_sweep.yaml")
    ap.add_argument("--out-root", default=None)
    ap.add_argument("--ollama-timeout-s", type=float, default=300.0)
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    run_id = _now_run_id()
    out_root = (
        Path(args.out_root)
        if args.out_root
        else Path("scripts/tr121/results/tr121_decode_sweep") / run_id
    )
    out_root.mkdir(parents=True, exist_ok=True)

    gen_tokens_list = [int(x) for x in (cfg.get("gen_tokens_list") or [])]
    if not gen_tokens_list:
        raise SystemExit("decode_sweep.yaml must contain gen_tokens_list")

    repetitions = int(cfg.get("repetitions") or 1)
    warmups = int(cfg.get("warmup_repetitions") or 0)
    seed = int(cfg.get("seed") or 0)
    scenarios = [str(s) for s in (cfg.get("scenarios") or [])]
    models = [str(m) for m in (cfg.get("models") or [])]
    backends = [str(b) for b in (cfg.get("backends") or [])]

    meta = {
        "run_id": run_id,
        "config_path": str(Path(args.config)),
        "run_name": cfg.get("run_name"),
        "gen_tokens_list": gen_tokens_list,
        "repetitions": repetitions,
        "warmup_repetitions": warmups,
        "seed": seed,
        "models": models,
        "backends": backends,
        "scenarios": scenarios,
    }
    (out_root / "manifest.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    run_scaling = _repo_root() / "scripts" / "tr121" / "run_scaling.py"
    analyze = _repo_root() / "scripts" / "tr121" / "analyze_scaling.py"

    rows: list[dict[str, Any]] = []
    frac_by_model: list[pd.DataFrame] = []
    frac_summary: list[pd.DataFrame] = []
    for gen in gen_tokens_list:
        out_dir = out_root / f"gen_{gen}"
        out_dir.mkdir(parents=True, exist_ok=True)
        cmd = [
            "python",
            str(run_scaling),
            "--config",
            str(Path("scripts/tr121/configs/scaling.yaml")),
            "--out-dir",
            str(out_dir),
            "--gen-tokens",
            str(gen),
            "--repetitions",
            str(repetitions),
            "--warmup-repetitions",
            str(warmups),
            "--seed",
            str(seed),
            "--models",
            ",".join(models),
            "--backends",
            ",".join(backends),
            "--scenarios",
            ",".join(scenarios),
            "--ollama-timeout-s",
            str(float(args.ollama_timeout_s)),
        ]
        subprocess.check_call(cmd, cwd=_repo_root())
        subprocess.check_call(
            ["python", str(analyze), "--run-dir", str(out_dir)],
            cwd=_repo_root(),
        )

        # Pull scenario-aggregated fits (geomean across scenarios).
        fits = pd.read_csv(out_dir / "analysis" / "scaling_fits.csv")
        sel = fits[(fits["scenario"] == "__all__") & (fits["aggregation"] == "geomean_across_scenarios")].copy()
        sel["gen_tokens_target"] = int(gen)
        rows.extend(sel.to_dict(orient="records"))

        per_model, summary = _decode_fraction_tables(run_dir=out_dir, gen_tokens_target=int(gen))
        frac_by_model.append(per_model)
        frac_summary.append(summary)

    _write_csv(out_root / "decode_sweep_summary.csv", rows)

    if frac_by_model:
        df_models = pd.concat(frac_by_model, ignore_index=True)
        df_models.to_csv(out_root / "decode_fraction_by_model.csv", index=False)
    else:
        df_models = pd.DataFrame()

    if frac_summary:
        df_summary = pd.concat(frac_summary, ignore_index=True)
        df_summary = (
            df_summary.groupby(["backend", "backend_kind", "gen_tokens_target"], dropna=False)
            .agg(
                n_models=("n_models", "max"),
                decode_fraction_median=("decode_fraction_median", "median"),
                decode_fraction_p25=("decode_fraction_p25", "median"),
                decode_fraction_p75=("decode_fraction_p75", "median"),
            )
            .reset_index()
            .sort_values(["backend_kind", "backend", "gen_tokens_target"])
        )
        df_summary.to_csv(out_root / "decode_fraction_summary.csv", index=False)

        plots_dir = out_root / "plots"
        plots_dir.mkdir(parents=True, exist_ok=True)
        if plt is not None:
            plt.figure(figsize=(9, 5))
            for backend, g in df_summary.groupby("backend", dropna=False):
                g = g.sort_values("gen_tokens_target")
                plt.plot(
                    g["gen_tokens_target"].to_numpy(),
                    g["decode_fraction_median"].to_numpy(),
                    marker="o",
                    label=str(backend),
                )
                plt.fill_between(
                    g["gen_tokens_target"].to_numpy(),
                    g["decode_fraction_p25"].to_numpy(),
                    g["decode_fraction_p75"].to_numpy(),
                    alpha=0.15,
                )
            plt.ylim(0.0, 1.0)
            plt.xlabel("gen_tokens")
            plt.ylabel("decode_fraction = kv_decode_ms / e2e_kv_ms")
            plt.title("Decode dominance vs generation length (median across models)")
            plt.grid(True, alpha=0.3)
            plt.legend(loc="lower right", fontsize=8)
            plt.tight_layout()
            plt.savefig(plots_dir / "decode_fraction_by_gen_tokens.png", dpi=160)
            plt.close()

    print(f"TR121 decode sweep written to: {out_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
