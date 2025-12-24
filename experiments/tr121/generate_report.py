#!/usr/bin/env python3
"""
TR121: Generate a first-pass Markdown report from a completed run directory.

This intentionally produces a narrative scaffold + key tables and links to artifacts.
For publish-ready quality, edit the output into PublishReady/reports/Technical_Report_121.md.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate TR121 report")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--out", default="reports/generated/Technical_Report_121.md")
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    manifest = _read_json(run_dir / "manifest.json")
    summary = pd.read_csv(run_dir / "analysis" / "summary_by_model_backend_mode.csv")
    summary_agg = None
    try:
        summary_agg = pd.read_csv(run_dir / "analysis" / "summary_by_model_backend_mode_agg.csv")
    except Exception:
        summary_agg = None
    fits = pd.read_csv(run_dir / "analysis" / "scaling_fits.csv")

    # Keep the report compact; publish-ready narrative is in PublishReady/*
    def _cell(v) -> str:
        if v is None:
            return ""
        if isinstance(v, float):
            if pd.isna(v):
                return ""
            return f"{v:.4g}"
        return str(v).replace("\n", " ").replace("|", "\\|")

    def table_md(df: pd.DataFrame, max_rows: int = 20) -> str:
        if df.shape[0] > max_rows:
            df = df.head(max_rows).copy()
        cols = list(df.columns)
        header = "| " + " | ".join(cols) + " |"
        sep = "| " + " | ".join(["---"] * len(cols)) + " |"
        rows = []
        for _, r in df.iterrows():
            rows.append("| " + " | ".join(_cell(r[c]) for c in cols) + " |")
        return "\n".join([header, sep] + rows)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines += [
        "# Technical Report 121 (Generated): Model Scaling Study",
        "",
        "**Status:** Generated draft (edit into `PublishReady/reports/Technical_Report_121.md`).",
        "",
        "## Run Metadata",
        "",
        f"- Run dir: `{run_dir.as_posix()}`",
        f"- Run id: `{manifest.get('run_id')}`",
        f"- Git head: `{manifest.get('git_head')}`",
        f"- Python: `{manifest.get('platform', {}).get('python')}`",
        f"- Torch: `{manifest.get('torch', {}).get('torch')}`",
        f"- Transformers: `{manifest.get('torch', {}).get('transformers')}`",
        f"- CUDA available: `{manifest.get('cuda_available')}`",
        f"- Gen tokens target: `{manifest.get('gen_tokens')}`",
        f"- Repetitions: `{manifest.get('repetitions')}` (warmups: `{manifest.get('warmup_repetitions')}`)",
        f"- Seed: `{manifest.get('seed')}`",
        "",
        "## Summary (scenario-level; first 20 rows)",
        "",
        table_md(
            summary[
                [
                    "backend",
                    "mode",
                    "scenario",
                    "model",
                    "params_millions_effective",
                    "latency_median_ms",
                    "tokens_per_s_median",
                    "n",
                ]
            ]
            .sort_values(["backend", "mode", "scenario", "params_millions_effective"])
            .reset_index(drop=True)
        ),
        "",
    ]

    if summary_agg is not None:
        lines += [
            "## Summary (scenario-aggregated; all rows)",
            "",
            table_md(
                summary_agg[
                    [
                        "backend",
                        "mode",
                        "model",
                        "params_millions_effective",
                        "latency_geomean_ms",
                        "tokens_per_s_geomean",
                    ]
                ].sort_values(["backend", "mode", "params_millions_effective"])
            ),
            "",
        ]

    lines += [
        "## Scaling Fits (power law; latency ~ params^slope)",
        "",
        table_md(
            (
                fits[
                    [
                        c
                        for c in [
                            "backend",
                            "mode",
                            "scenario",
                            "aggregation",
                            "n_models",
                            "ok",
                            "slope",
                            "slope_ci_low",
                            "slope_ci_high",
                            "r2",
                        ]
                        if c in fits.columns
                    ]
                ].sort_values(["backend", "mode", "scenario"])
            )
        ),
        "",
        "## Artifacts",
        "",
        f"- Raw per-measurement table: `{(run_dir / 'metrics.csv').as_posix()}`",
        f"- Aggregated summary: `{(run_dir / 'analysis' / 'summary_by_model_backend_mode.csv').as_posix()}`",
        f"- Aggregated summary (scenario-agg): `{(run_dir / 'analysis' / 'summary_by_model_backend_mode_agg.csv').as_posix()}`",
        f"- Scaling fits: `{(run_dir / 'analysis' / 'scaling_fits.csv').as_posix()}`",
        f"- Warmup effect: `{(run_dir / 'analysis' / 'warmup_effect.csv').as_posix()}`",
        f"- Plots: `{(run_dir / 'analysis' / 'plots').as_posix()}`",
        "",
    ]

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
