#!/usr/bin/env python3
"""
TR118: Publish-ready report generator.

Consumes TR118 artifacts under `scripts/tr118/results/` and writes a Markdown
report under `reports/generated/`.

This is local-first: if some artifacts are missing (e.g., TensorRT on Windows),
the report will include an explicit "Missing Data" section instead of guessing.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
from typing import Any

import pandas as pd
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.tr117.statistical_analysis import compute_summary
from scripts.tr118.artifact_utils import resolve_repo_path


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _git_sha() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip() or None
    except Exception:
        return None


def _latest_file(glob: list[Path]) -> Path | None:
    files = sorted(glob, key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _md_table(headers: list[str], rows: list[list[Any]]) -> str:
    def fmt(x: Any) -> str:
        if x is None:
            return "N/A"
        if isinstance(x, float):
            return f"{x:.4g}"
        return str(x)

    out = []
    out.append("| " + " | ".join(headers) + " |")
    out.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for r in rows:
        out.append("| " + " | ".join(fmt(x) for x in r) + " |")
    return "\n".join(out)


def _load_raw_jsonl(path: Path) -> pd.DataFrame:
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        records.append(json.loads(line))
    df = pd.DataFrame(records)
    df["backend"] = df["spec"].apply(lambda s: s["backend"])
    df["scenario"] = df["spec"].apply(lambda s: s["scenario"])
    df["status"] = df["status"].astype(str)
    df["degraded"] = df.apply(
        lambda r: bool(r.get("degraded_count", 0) > 0) or str(r.get("status", "")) != "ok",
        axis=1,
    )
    df["run_mean_latency_ms"] = df["latencies_ms"].apply(
        lambda xs: float(sum(xs) / len(xs)) if isinstance(xs, list) and xs else None
    )
    if "ttft_ms" in df.columns:
        df["run_mean_ttft_ms"] = df["ttft_ms"].apply(
            lambda xs: float(sum(xs) / len(xs)) if isinstance(xs, list) and xs else None
        )
    else:
        df["run_mean_ttft_ms"] = None
    df["run_mean_throughput_tok_s"] = df["throughput_tok_s"].apply(
        lambda xs: float(sum(xs) / len(xs)) if isinstance(xs, list) and xs else None
    )
    return df


def _overall_backend_table(df: pd.DataFrame) -> str:
    df_ok = df[(df["run_mean_latency_ms"].notna()) & (df["degraded"] == False)]  # noqa: E712
    rows = []
    for backend, group in df.groupby("backend"):
        total = int(group.shape[0])
        degraded = int(group["degraded"].astype(int).sum())
        ok = total - degraded
        ok_group = df_ok[df_ok["backend"] == backend]
        lat_vals = [float(v) for v in ok_group["run_mean_latency_ms"].tolist()]
        thr_vals = [float(v) for v in ok_group["run_mean_throughput_tok_s"].dropna().tolist()]
        lat = compute_summary(lat_vals) if lat_vals else None
        thr = compute_summary(thr_vals) if thr_vals else None
        rows.append(
            [
                backend,
                ok,
                total,
                degraded / total if total else None,
                lat.mean if lat else None,
                f"[{lat.ci_lower:.4g}, {lat.ci_upper:.4g}]" if lat else None,
                thr.mean if thr else None,
                f"[{thr.ci_lower:.4g}, {thr.ci_upper:.4g}]" if thr else None,
            ]
        )
    rows.sort(key=lambda r: (r[4] if r[4] is not None else 1e18))
    return _md_table(
        [
            "Backend",
            "n_ok",
            "n_total",
            "degraded_rate",
            "lat_mean_ms",
            "lat_ci95",
            "thr_mean_tok_s",
            "thr_ci95",
        ],
        rows,
    )


def _overall_ttft_table(df: pd.DataFrame) -> str:
    df_ok = df[(df["run_mean_ttft_ms"].notna()) & (df["degraded"] == False)]  # noqa: E712
    rows = []
    for backend, group in df_ok.groupby("backend"):
        vals = [float(v) for v in group["run_mean_ttft_ms"].dropna().tolist()]
        summary = compute_summary(vals) if vals else None
        rows.append(
            [
                backend,
                len(vals),
                summary.mean if summary else None,
                f"[{summary.ci_lower:.4g}, {summary.ci_upper:.4g}]" if summary else None,
                summary.median if summary else None,
            ]
        )
    rows.sort(key=lambda r: (r[2] if r[2] is not None else 1e18))
    return _md_table(["Backend", "n_ok", "ttft_mean_ms", "ttft_ci95", "ttft_median_ms"], rows)


def _resource_summary_table(df: pd.DataFrame) -> str:
    if "resource_metrics" not in df.columns:
        return "_No resource telemetry captured (resource_metrics missing)._"

    df_ok = df[(df["degraded"] == False)]  # noqa: E712
    rows: list[list[Any]] = []

    def _mean_of(metrics: list[dict[str, Any]], key: str) -> float | None:
        vals: list[float] = []
        for m in metrics:
            v = m.get(key)
            if isinstance(v, (int, float)):
                vals.append(float(v))
        if not vals:
            return None
        return float(sum(vals) / len(vals))

    for backend, group in df_ok.groupby("backend"):
        metrics = [m for m in group["resource_metrics"].tolist() if isinstance(m, dict)]
        rows.append(
            [
                backend,
                int(group.shape[0]),
                _mean_of(metrics, "gpu_power_mean_watts"),
                _mean_of(metrics, "gpu_memory_peak_mb"),
                _mean_of(metrics, "gpu_temperature_peak_c"),
                _mean_of(metrics, "cpu_memory_peak_mb"),
            ]
        )

    rows.sort(key=lambda r: str(r[0]))
    return _md_table(
        ["Backend", "n_ok", "gpu_power_mean_w", "gpu_mem_peak_mb", "gpu_temp_peak_c", "cpu_mem_peak_mb"],
        rows,
    )


def _comparisons_table(comparisons: list[dict[str, Any]], limit: int = 20) -> str:
    rows: list[list[Any]] = []
    for c in (comparisons or [])[:limit]:
        rows.append(
            [
                c.get("group_a"),
                c.get("group_b"),
                c.get("metric"),
                c.get("mean_a"),
                c.get("mean_b"),
                c.get("percent_change"),
                c.get("p_value"),
                c.get("effect_size"),
                c.get("significant"),
            ]
        )
    return _md_table(
        [
            "baseline",
            "candidate",
            "metric",
            "mean_a",
            "mean_b",
            "pct_change",
            "p_value",
            "cohens_d",
            "significant",
        ],
        rows,
    )


def _fmt_counts(d: Any, limit: int = 8) -> str:
    if not isinstance(d, dict) or not d:
        return "N/A"
    items = sorted(((str(k), v) for k, v in d.items()), key=lambda kv: kv[0])
    parts = [f"{k}={v}" for k, v in items[:limit]]
    if len(items) > limit:
        parts.append("…")
    return ", ".join(parts)


def _rel_md_path(from_dir: Path, target: Path) -> str:
    rel = os.path.relpath(target, from_dir)
    return Path(rel).as_posix()


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate TR118 report from artifacts")
    parser.add_argument(
        "--config",
        default="scripts/tr118/configs/matrix_postdoc.yaml",
        help="TR118 config yaml",
    )
    parser.add_argument(
        "--output",
        default="reports/generated/Technical_Report_118.md",
        help="Output report path",
    )
    parser.add_argument(
        "--manifest",
        default=None,
        help="Experiment manifest JSON (defaults to latest under results/processed)",
    )
    parser.add_argument(
        "--modes",
        nargs="*",
        choices=["prefill", "generate"],
        default=None,
        help="Modes to include (defaults to manifest.runs keys or config.benchmark.modes)",
    )
    parser.add_argument(
        "--raw",
        default=None,
        help="Override raw JSONL path (applies to the first mode only)",
    )
    args = parser.parse_args()

    cfg_path = resolve_repo_path(_REPO_ROOT, str(args.config))
    cfg = _load_yaml(cfg_path)
    results_dir = resolve_repo_path(_REPO_ROOT, str(cfg["output"]["results_dir"]))
    processed_dir = results_dir / "processed"

    manifest_path = (
        resolve_repo_path(_REPO_ROOT, str(args.manifest))
        if args.manifest
        else _latest_file(list(processed_dir.glob("experiment_manifest_*.json")))
    )
    manifest = _read_json(manifest_path) if manifest_path and manifest_path.exists() else None

    modes = args.modes
    if not modes:
        if manifest and isinstance(manifest.get("runs"), dict) and manifest.get("runs"):
            modes = [str(k) for k in manifest["runs"].keys()]
        else:
            cfg_modes = cfg.get("benchmark", {}).get("modes")
            if isinstance(cfg_modes, list) and cfg_modes:
                modes = [str(m) for m in cfg_modes]
            else:
                modes = [str(cfg.get("benchmark", {}).get("mode", "prefill"))]

    out_path = resolve_repo_path(_REPO_ROOT, str(args.output))
    out_path.parent.mkdir(parents=True, exist_ok=True)

    prompt_cfg = None
    if manifest and manifest.get("prompt_config_path"):
        prompt_cfg = str(manifest["prompt_config_path"])
    else:
        prompt_cfg = str(cfg.get("benchmark", {}).get("prompt_config_path", "scripts/tr117/configs/matrix_tier3.yaml"))

    title = "# Technical Report 118: ONNX Runtime + TensorRT Deep Dive\n"
    report_status = "Draft (auto-generated from artifacts)"
    meta_lines = [
        "",
        "**Version:** 1.0",
        f"**Date:** {time.strftime('%Y-%m-%d')}",
        f"**Status:** {report_status}",
        f"**Git SHA:** `{_git_sha() or 'unknown'}`",
        "",
    ]

    abstract = [
        "## Abstract",
        "",
        "TR118 deep-dives ONNX Runtime and TensorRT for local-first LLM inference, closing the TR117 gap where ONNX/TRT runs were fully degraded.",
        "We report performance, degraded-rate, and accuracy (perplexity) gates, using artifact-driven reproducibility (JSONL + CSV + manifests).",
        "",
    ]

    introduction = [
        "## Introduction",
        "",
        "- TR117 established a cross-backend baseline and identified ONNX/TRT infrastructure failures.",
        "- TR118 focuses on making ONNX export + TRT engine builds real and measurable, with explicit degraded reasons and accuracy gates.",
        "",
    ]

    methodology = [
        "## Methodology",
        "",
        "### Metrics",
        "- Latency (ms), throughput (tok/s), degraded rate.",
        "- Generation mode (if enabled) uses an uncached greedy loop (repeated full forward passes).",
        "",
        "### Accuracy Gate",
        "- Perplexity on WikiText-2 vs PyTorch baseline with per-precision thresholds.",
        "",
        "### Statistical Analysis",
        "- 95% confidence intervals + t-tests + Cohen's d via TR117 helpers.",
        "",
    ]

    experiment = [
        "## Experimental Design",
        "",
        f"- Config: `{cfg_path}`",
        f"- Prompt config: `{prompt_cfg}`",
        f"- Modes: {', '.join(modes)}",
        f"- Backends: {', '.join(str(b) for b in cfg.get('benchmark', {}).get('backends', []))}",
        f"- Scenarios: {', '.join(str(s) for s in cfg.get('benchmark', {}).get('scenarios', []))}",
        f"- Repetitions: {int(cfg.get('benchmark', {}).get('repetitions', 0) or 0)}",
        "",
        f"**Artifacts root:** `{results_dir}`",
        "",
    ]

    if manifest_path:
        experiment += [
            "### Run Manifest",
            "",
            f"- Manifest: `{manifest_path}`",
            f"- Duration (s): {manifest.get('duration_s') if isinstance(manifest, dict) else 'N/A'}",
            "",
        ]

    missing: list[str] = []

    # Global artifacts
    ppl_path = processed_dir / "perplexity_results.csv"
    if isinstance(manifest, dict) and manifest.get("perplexity_results_csv"):
        ppl_path = resolve_repo_path(_REPO_ROOT, str(manifest["perplexity_results_csv"]))

    ppl_json_path = processed_dir / "perplexity_results.json"
    if isinstance(manifest, dict) and manifest.get("perplexity_results_json"):
        ppl_json_path = resolve_repo_path(_REPO_ROOT, str(manifest["perplexity_results_json"]))

    export_meta_path = processed_dir / "export_metadata.json"
    if isinstance(manifest, dict) and manifest.get("export_metadata_path"):
        export_meta_path = resolve_repo_path(_REPO_ROOT, str(manifest["export_metadata_path"]))
    else:
        export_meta_path = _latest_file(list(processed_dir.glob("export_metadata*.json"))) or export_meta_path

    trt_build_path = processed_dir / "trt_build_metadata.json"
    if isinstance(manifest, dict) and manifest.get("trt_build_metadata_path"):
        trt_build_path = resolve_repo_path(_REPO_ROOT, str(manifest["trt_build_metadata_path"]))
    else:
        trt_build_path = _latest_file(list(processed_dir.glob("trt_build_metadata*.json"))) or trt_build_path

    ppl_df = pd.read_csv(ppl_path) if ppl_path.exists() else None
    if ppl_df is None:
        missing.append(str(ppl_path))

    ppl_json = _read_json(ppl_json_path) if ppl_json_path.exists() else None
    if ppl_json is None:
        missing.append(str(ppl_json_path))

    export_meta = _read_json(export_meta_path) if export_meta_path.exists() else None
    if export_meta is None:
        missing.append(str(export_meta_path))

    trt_build_meta = _read_json(trt_build_path) if trt_build_path.exists() else None
    if trt_build_meta is None:
        missing.append(str(trt_build_path))

    plots_dir = results_dir / "plots"

    results_sections: list[str] = ["## Results"]
    raw_by_mode: dict[str, pd.DataFrame | None] = {}

    runs = manifest.get("runs", {}) if isinstance(manifest, dict) else {}

    for i, mode in enumerate(modes):
        results_sections += ["", f"### Mode: `{mode}`", ""]

        raw_path = None
        if isinstance(runs, dict):
            run_entry = runs.get(mode, {}) if isinstance(runs.get(mode, {}), dict) else {}
            raw_entry = run_entry.get("raw_results_path")
            if raw_entry:
                raw_path = resolve_repo_path(_REPO_ROOT, str(raw_entry))
        if raw_path is None:
            if args.raw and i == 0:
                raw_path = resolve_repo_path(_REPO_ROOT, str(args.raw))
            else:
                raw_path = _latest_file(list((results_dir / "raw").glob(f"bench_{mode}_*.jsonl")))

        summary_path = processed_dir / f"latency_summary_{mode}.csv"
        stats_path = processed_dir / f"statistical_analysis_{mode}.json"
        if isinstance(runs, dict):
            run_entry = runs.get(mode, {}) if isinstance(runs.get(mode, {}), dict) else {}
            if run_entry.get("latency_summary_path"):
                summary_path = resolve_repo_path(_REPO_ROOT, str(run_entry["latency_summary_path"]))
            if run_entry.get("statistical_analysis_path"):
                stats_path = resolve_repo_path(_REPO_ROOT, str(run_entry["statistical_analysis_path"]))

        df_raw = (
            _load_raw_jsonl(raw_path)
            if raw_path and raw_path.exists() and raw_path.stat().st_size > 0
            else None
        )
        raw_by_mode[str(mode)] = df_raw
        if df_raw is None:
            missing.append(f"raw_jsonl:{mode}")
            results_sections += ["_No raw benchmark data found for this mode._", ""]
        else:
            results_sections += ["#### Overall Backend Summary (Run-Level)", "", _overall_backend_table(df_raw), ""]
            if df_raw["run_mean_ttft_ms"].notna().any():
                results_sections += ["#### TTFT Summary (Run-Level)", "", _overall_ttft_table(df_raw), ""]
            if "resource_metrics" in df_raw.columns:
                results_sections += ["#### Resource Summary (Run-Level)", "", _resource_summary_table(df_raw), ""]

        if summary_path.exists():
            results_sections += [f"- Summary CSV: `{summary_path}`", ""]
        else:
            missing.append(f"latency_summary_csv:{mode}")
            results_sections += [f"_Missing `{summary_path}`._", ""]

        stats = _read_json(stats_path) if stats_path.exists() else None
        if stats is None:
            missing.append(f"statistical_analysis_json:{mode}")
        else:
            comps = stats.get("comparisons") if isinstance(stats, dict) else None
            if isinstance(comps, list) and comps:
                results_sections += ["#### Baseline Comparisons (Overall)", "", _comparisons_table(comps), ""]

        # Inline plots when present.
        fig_latency = plots_dir / f"mean_latency_{mode}.png"
        fig_thr = plots_dir / f"mean_throughput_tok_s_{mode}.png"
        fig_degr = plots_dir / f"degraded_rate_{mode}.png"
        figs = [p for p in (fig_latency, fig_thr, fig_degr) if p.exists()]
        if figs:
            results_sections += ["#### Figures", ""]
            for p in figs:
                rel = _rel_md_path(out_path.parent, p)
                results_sections += [f"![{p.stem}]({rel})", ""]

    def _mode_best_backend(df: pd.DataFrame | None) -> tuple[str, float] | None:
        if df is None or df.empty:
            return None
        df_ok = df[(df["run_mean_latency_ms"].notna()) & (df["degraded"] == False)]  # noqa: E712
        if df_ok.empty:
            return None
        means = df_ok.groupby("backend")["run_mean_latency_ms"].mean()
        if means.empty:
            return None
        best_backend = str(means.idxmin())
        return best_backend, float(means.loc[best_backend])

    def _mode_baseline_latency(df: pd.DataFrame | None, baseline_backend: str) -> float | None:
        if df is None or df.empty:
            return None
        df_ok = df[(df["run_mean_latency_ms"].notna()) & (df["degraded"] == False)]  # noqa: E712
        if df_ok.empty:
            return None
        sub = df_ok[df_ok["backend"] == baseline_backend]
        if sub.empty:
            return None
        return float(sub["run_mean_latency_ms"].mean())

    def _pct_change(baseline: float | None, candidate: float | None) -> float | None:
        if baseline is None or candidate is None or baseline == 0:
            return None
        return float((candidate - baseline) / baseline * 100.0)

    total_records = sum(int(df.shape[0]) for df in raw_by_mode.values() if df is not None)
    total_degraded = sum(
        int(df["degraded"].astype(bool).sum())
        for df in raw_by_mode.values()
        if df is not None and "degraded" in df.columns
    )
    any_degraded = total_degraded > 0
    all_ppl_pass = bool(ppl_df is not None and "pass" in ppl_df.columns and ppl_df["pass"].astype(bool).all())

    sanity_warnings: list[str] = []
    if isinstance(trt_build_meta, list):
        for r in trt_build_meta:
            if not isinstance(r, dict):
                continue
            if str(r.get("precision", "")).lower() != "int8":
                continue
            eng = r.get("engine_inspect") if isinstance(r.get("engine_inspect"), dict) else {}
            insp = eng.get("engine_inspector") if isinstance(eng.get("engine_inspector"), dict) else {}
            has_int8 = bool(insp.get("has_int8_in_json") or eng.get("has_int8_tensors"))
            if not has_int8:
                sanity_warnings.append(
                    "TensorRT INT8 engine inspector does not report INT8 coverage; treat INT8 claims as unverified (likely FP16/FP32 fallback)."
                )
            calib = r.get("int8_calibration") if isinstance(r.get("int8_calibration"), dict) else {}
            if calib and str(calib.get("source")) == "random":
                sanity_warnings.append(
                    "TensorRT INT8 calibration used random tokens (datasets/tokenizer unavailable); accuracy/INT8 behavior is not publishable."
                )
    if isinstance(ppl_json, dict):
        diag = ppl_json.get("diagnostics") if isinstance(ppl_json.get("diagnostics"), dict) else {}
        diffs = diag.get("logit_diffs_last_token") if isinstance(diag.get("logit_diffs_last_token"), dict) else {}
        int8 = diffs.get("tensorrt-int8") if isinstance(diffs.get("tensorrt-int8"), dict) else None
        if isinstance(int8, dict) and float(int8.get("max_abs", 0.0) or 0.0) == 0.0:
            sanity_warnings.append("tensorrt-int8 last-token logit diff vs PyTorch is 0.0; suspect fallback/caching/measurement bug.")

    sanity_ok = not sanity_warnings
    if not missing and total_records > 0 and not any_degraded and all_ppl_pass:
        report_status = "Complete (artifact-driven)" if sanity_ok else "Draft (sanity checks failed)"
        meta_lines[3] = f"**Status:** {report_status}"

    baseline_backend = str(cfg.get("baseline", {}).get("backend", "transformers-gpu-compile"))
    degraded_rate = (float(total_degraded) / float(total_records)) if total_records else 0.0
    exec_lines: list[str] = [
        "## Executive Summary",
        "",
        "### Key Findings",
        "",
        f"- Reliability: {total_records} run-level records across {', '.join(modes)}; degraded-rate = {degraded_rate:.1%} ({total_degraded}/{total_records})",
        f"- Accuracy: perplexity gate {'passed' if all_ppl_pass else 'not fully satisfied'} (see `{ppl_path}`)",
    ]
    for mode in modes:
        df = raw_by_mode.get(str(mode))
        best = _mode_best_backend(df)
        base_lat = _mode_baseline_latency(df, baseline_backend=baseline_backend)
        if best is None:
            continue
        best_backend, best_lat = best
        delta = _pct_change(base_lat, best_lat)
        delta_str = f"{delta:.2f}%" if delta is not None else "N/A"
        exec_lines.append(
            f"- {mode}: best mean latency = {best_backend} ({best_lat:.3g} ms), vs baseline {baseline_backend} ({base_lat:.3g} ms, {delta_str})"
            if base_lat is not None
            else f"- {mode}: best mean latency = {best_backend} ({best_lat:.3g} ms)"
        )

    if platform.system() == "Windows":
        exec_lines += [
            "- Note: PyTorch `transformers-gpu-compile` uses `torch.compile(..., backend=\"cudagraphs\", dynamic=False)` on Windows (no Triton).",
        ]
    exec_lines += [
        "",
        "### Honest Limitations",
        "",
        "- `generate` mode is an uncached greedy loop (`use_cache=False`) and is not representative of KV-cached decoding throughput.",
        "- `models/tiny-gpt2` in this repo is a toy/untrained model; perplexity is expected to be near-uniform (~vocab) and accuracy deltas mainly reflect numerical consistency.",
        "- Single model (gpt2/124M) and single machine; results may not generalize to larger models (see TR121).",
        "- Latency excludes end-to-end serving overhead (tokenization, networking, batching policies).",
        "",
    ]

    env_lines: list[str] = []
    if isinstance(manifest, dict):
        plat = manifest.get("platform")
        pkgs = manifest.get("package_versions")
        if isinstance(plat, dict):
            env_lines = ["## Environment", ""]
            if plat.get("os"):
                env_lines.append(f"- OS: {plat.get('os')}")
            if plat.get("python"):
                env_lines.append(f"- Python: {plat.get('python')}")
            cuda_dev = plat.get("cuda_device")
            if isinstance(cuda_dev, dict) and cuda_dev.get("name"):
                env_lines.append(
                    f"- GPU: {cuda_dev.get('name')} ({cuda_dev.get('total_memory_mb', 'N/A'):.0f} MB, CC {cuda_dev.get('capability', 'N/A')})"
                    if isinstance(cuda_dev.get("total_memory_mb"), (int, float))
                    else f"- GPU: {cuda_dev.get('name')} (CC {cuda_dev.get('capability', 'N/A')})"
                )
            ort_providers = plat.get("onnxruntime_providers")
            if isinstance(ort_providers, list) and ort_providers:
                env_lines.append(f"- ONNXRuntime providers: {', '.join(str(p) for p in ort_providers)}")
            if isinstance(pkgs, dict):
                key_pkgs = ["torch", "transformers", "onnxruntime", "tensorrt"]
                kv = [f"{k}={pkgs.get(k)}" for k in key_pkgs if pkgs.get(k)]
                if kv:
                    env_lines.append(f"- Key packages: {', '.join(kv)}")
            env_lines += [""]

    if ppl_df is not None:
        rows = []
        for r in ppl_df.to_dict(orient="records"):
            rows.append(
                [
                    r.get("backend"),
                    r.get("perplexity"),
                    r.get("delta_frac"),
                    r.get("threshold"),
                    r.get("pass"),
                    r.get("error"),
                ]
            )
        results_sections += [
            "### Accuracy (Perplexity Gate)",
            "",
            f"- Results CSV: `{ppl_path}`",
            f"- Diagnostics JSON: `{ppl_json_path}`" if ppl_json_path else "",
            "",
            _md_table(["Backend", "PPL", "delta_frac", "Threshold", "Pass", "Error"], rows),
            "",
        ]

    sanity_sections: list[str] = []
    if export_meta or trt_build_meta or ppl_json:
        sanity_sections = ["## Sanity Checks", ""]

        if export_meta:
            onnx_inspect = export_meta.get("onnx_inspect") if isinstance(export_meta.get("onnx_inspect"), dict) else {}
            weights = export_meta.get("model_weight_files") if isinstance(export_meta.get("model_weight_files"), dict) else {}
            sanity_sections += [
                "### Model / ONNX Artifacts",
                "",
                _md_table(
                    ["Field", "Value"],
                    [
                        ["model", cfg.get("model", {}).get("name")],
                        ["onnx_path", export_meta.get("output_path")],
                        ["onnx_sha256", export_meta.get("onnx_sha256")],
                        ["onnx_file_size_mb", onnx_inspect.get("onnx_file_size_mb")],
                        ["external_data", onnx_inspect.get("external_data")],
                        ["external_total_mb", onnx_inspect.get("external_total_size_mb")],
                        ["total_artifact_mb", onnx_inspect.get("total_artifact_size_mb")],
                        ["initializer_numel_est", onnx_inspect.get("initializer_numel")],
                        ["initializer_bytes_est_mb", onnx_inspect.get("initializer_bytes_est_mb")],
                        ["weight_files_total_mb", weights.get("total_size_mb")],
                    ],
                ),
                "",
            ]
            if isinstance(weights.get("weight_files"), list) and weights["weight_files"]:
                wf = []
                for f in weights["weight_files"][:6]:
                    if not isinstance(f, dict):
                        continue
                    wf.append(f"{Path(str(f.get('path'))).name}: {f.get('size_mb')}")
                sanity_sections += ["- Weight files: " + ", ".join(wf), ""]

        if isinstance(trt_build_meta, list) and trt_build_meta:
            rows = []
            for r in trt_build_meta:
                if not isinstance(r, dict):
                    continue
                eng = r.get("engine_inspect") if isinstance(r.get("engine_inspect"), dict) else {}
                insp = eng.get("engine_inspector") if isinstance(eng.get("engine_inspector"), dict) else {}
                calib = r.get("int8_calibration") if isinstance(r.get("int8_calibration"), dict) else {}
                rows.append(
                    [
                        r.get("precision"),
                        r.get("file_size_mb"),
                        eng.get("num_layers"),
                        insp.get("layer_entry_type"),
                        insp.get("has_int8_in_json"),
                        eng.get("has_int8_tensors"),
                        _fmt_counts(eng.get("layer_output_dtype_counts")),
                        calib.get("source") if calib else None,
                        calib.get("cache_hit_before") if calib else None,
                    ]
                )
            sanity_sections += [
                "### TensorRT Engine Inspection",
                "",
                _md_table(
                    [
                        "Precision",
                        "Plan_MB",
                        "Layers",
                        "InspectorType",
                        "INT8_in_JSON",
                        "INT8_tensors",
                        "OutputDTypes",
                        "CalibSource",
                        "CalibCacheHit",
                    ],
                    rows,
                ),
                "",
            ]

        if isinstance(ppl_json, dict):
            diag = ppl_json.get("diagnostics") if isinstance(ppl_json.get("diagnostics"), dict) else {}
            base = diag.get("baseline") if isinstance(diag.get("baseline"), dict) else {}
            ref = diag.get("reference_check_pytorch_loss") if isinstance(diag.get("reference_check_pytorch_loss"), dict) else {}
            sanity_sections += [
                "### Perplexity Correctness",
                "",
                _md_table(
                    ["Field", "Value"],
                    [
                        ["baseline_ppl", base.get("perplexity")],
                        ["baseline_mean_nll", base.get("mean_nll")],
                        ["baseline_token_count", base.get("token_count")],
                        ["ln_vocab", diag.get("ln_vocab")],
                        ["expected_uniform_ppl", diag.get("expected_uniform_perplexity")],
                        ["ref_loss_mean_nll", ref.get("mean_nll") if isinstance(ref, dict) else None],
                        ["ref_loss_ppl", ref.get("perplexity") if isinstance(ref, dict) else None],
                    ],
                ),
                "",
            ]
            diffs = diag.get("logit_diffs_last_token") if isinstance(diag.get("logit_diffs_last_token"), dict) else {}
            if diffs:
                rows = []
                for k, v in diffs.items():
                    if not isinstance(v, dict):
                        continue
                    rows.append([k, v.get("mean_abs"), v.get("max_abs"), v.get("providers_used"), v.get("error")])
                sanity_sections += [
                    "### Logit Diffs vs PyTorch (Last Token)",
                    "",
                    _md_table(["Backend", "mean_abs", "max_abs", "providers_used", "error"], rows),
                    "",
                ]

        if sanity_warnings:
            sanity_sections += ["### Sanity Warnings", "", *[f"- {w}" for w in sanity_warnings], ""]

    if export_meta:
        results_sections += [
            "### Export Overhead (ONNX)",
            "",
            _md_table(
                ["Field", "Value"],
                [
                    ["onnx_path", export_meta.get("output_path")],
                    ["export_time_s", export_meta.get("export_time_s")],
                    ["file_size_mb", export_meta.get("file_size_mb")],
                    ["opset_version", export_meta.get("opset_version")],
                    ["dynamic_axes", export_meta.get("dynamic_axes")],
                    ["trt_friendly_inputs", export_meta.get("trt_friendly_inputs")],
                    ["reused", export_meta.get("reused")],
                    ["valid", export_meta.get("valid")],
                    ["onnx_sha256", export_meta.get("onnx_sha256")],
                ],
            ),
            "",
        ]

    if isinstance(trt_build_meta, list) and trt_build_meta:
        rows = []
        for r in trt_build_meta:
            rows.append(
                [
                    r.get("precision"),
                    Path(str(r.get("output_path"))).name if r.get("output_path") else None,
                    r.get("built"),
                    r.get("reused"),
                    r.get("build_time_s"),
                    r.get("file_size_mb"),
                    r.get("dynamic_shapes"),
                    r.get("profiles"),
                    r.get("error"),
                ]
            )
        results_sections += [
            "### TensorRT Build Overhead",
            "",
            f"- Build metadata: `{trt_build_path}`",
            "",
            _md_table(
                ["Precision", "Plan", "Built", "Reused", "Build s", "Size MB", "Dynamic", "Profiles", "Error"],
                rows,
            ),
            "",
        ]

    discussion = [
        "## Discussion",
        "",
        "### Interpretation",
        "- This run demonstrates that ONNX export + TensorRT engine builds can be made reliable on a single Windows + CUDA workstation.",
        "- For this tiny model and short prompts, ORT-CPU can win on latency due to reduced GPU launch/dispatch overhead; larger models should re-test (TR121).",
        "- TensorRT build cost is non-trivial; treat it as an offline step that must be amortized for production value.",
        "",
        "### Limitations / Threats to Validity",
        "- See `Executive Summary: Honest Limitations` for the primary caveats.",
        "",
    ]

    conclusions = [
        "## Conclusions",
        "",
        "TR118 provides an artifact-driven pipeline for measuring ONNX Runtime and TensorRT locally, including degraded-rate accounting, build/export metadata, and perplexity gates.",
        "",
        "## Recommendations",
        "",
        "- If you need portability/simplicity: start with ONNX Runtime (CPU or CUDA EP).",
        "- If you can prebuild engines and need maximum GPU throughput: TensorRT (FP16/INT8 as permitted by accuracy gates).",
        "- Keep PyTorch as the reference baseline; on Windows prefer `torch.compile(..., backend=\"cudagraphs\", dynamic=False)` for stability.",
        "",
    ]

    reproducibility = [
        "## Reproducibility",
        "",
        "Run the full pipeline:",
        "",
        "```bash",
        f"python scripts/tr118/run_experiment.py --config {cfg_path} --device cuda",
        "```",
        "",
        "Generate this report from artifacts:",
        "",
        "```bash",
        f"python scripts/tr118/generate_report.py --config {cfg_path} --manifest {manifest_path or ''}".rstrip(),
        "```",
        "",
    ]

    appendix = [
        "## Appendix",
        "",
        f"- Artifacts root: `{results_dir}`",
        f"- Processed dir: `{processed_dir}`",
        "",
    ]

    missing_section: list[str] = []
    if missing:
        missing_section = [
            "## Missing Data / Notes",
            "",
            "The following artifacts were not found, so sections were left incomplete:",
            "",
            *[f"- `{m}`" for m in missing],
            "",
        ]

    out_md = "\n".join(
        [
            title,
            *meta_lines,
            *abstract,
            *exec_lines,
            *introduction,
            *methodology,
            *experiment,
            *env_lines,
            *sanity_sections,
            *results_sections,
            *discussion,
            *conclusions,
            *reproducibility,
            *appendix,
            *missing_section,
        ]
    ).strip() + "\n"

    out_path.write_text(out_md, encoding="utf-8")
    print(f"Wrote report to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
