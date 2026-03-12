#!/usr/bin/env python3
"""TR126 Phase 2: Generate markdown report from analysis results.

Produces a 9-section report from phase2_analysis.json:
  1.  Environment — GPU, CUDA, Triton, Docker
  2.  Methodology — experiment design, sample counts, modes, key changes
  3.  Cross-Phase Validation — Phase 1 gate status
  4-6. Per-mode results (one section per mode):
      - Backend summary table with CI
      - Per-model breakdown table
      - Compile paradox assessment (aggregate + per-scenario)
      - Pairwise comparisons
      - Outlier analysis
      - Cross-platform comparison (if Windows baseline available)
  7.  Power Analysis — minimum detectable effect with practical ms interpretation
  8.  Data-Driven Findings — computed from all mode results
  9.  Conclusions & Implications — synthesized across modes

All findings are derived from analysis data — no hard-coded assumptions.

Usage:
    python research/tr126/phase2/generate_report.py [--results-dir DIR] [-v]
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import UTC, datetime
import json
import logging
from pathlib import Path
import sys
from typing import Any

_DIR = Path(__file__).resolve().parent
_REPO = _DIR.parents[2]
sys.path.insert(0, str(_REPO))

from research.tr126.shared.utils import find_latest_run

logger = logging.getLogger("tr126.phase2.report")


def _load_json(path: Path) -> dict:
    """Load a JSON file, returning empty dict on failure."""
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _w(lines: list[str], text: str = "") -> None:
    """Append a line to the report."""
    lines.append(text)


def _fmt(val: float, decimals: int = 3) -> str:
    """Format float, returning 'N/A' for NaN values."""
    if val != val:  # NaN check
        return "N/A"
    return f"{val:.{decimals}f}"


def _effect_label(d: float) -> str:
    """Classify Cohen's d magnitude."""
    d = abs(d)
    if d < 0.2:
        return "negligible"
    if d < 0.5:
        return "small"
    if d < 0.8:
        return "medium"
    return "large"


# ---------------------------------------------------------------------------
# Per-model breakdown rendering
# ---------------------------------------------------------------------------


def _render_model_breakdown(
    lines: list[str],
    by_model_backend: dict[str, Any],
    section_prefix: str,
) -> None:
    """Render per-model × backend table from analysis data.

    Groups entries by model, showing a table per model with backend rows.
    """
    if not by_model_backend:
        return

    # Group by model
    models: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    for key, stats in by_model_backend.items():
        parts = key.rsplit("/", 1)
        if len(parts) == 2:
            model, backend = parts
            models[model].append((backend, stats))

    if not models:
        return

    _w(lines, f"### {section_prefix} Per-Model Breakdown")
    _w(lines)

    for model, entries in sorted(models.items()):
        _w(lines, f"**{model}:**")
        _w(lines)
        _w(lines, "| Backend | N | Mean (ms) | Median (ms) | p95 (ms) | 95% CI |")
        _w(lines, "|---------|---|-----------|-------------|----------|--------|")
        # Sort by mean latency
        entries.sort(key=lambda e: e[1].get("mean_ms", float("inf")))
        for backend, s in entries:
            ci_str = f"[{_fmt(s.get('ci_lower', float('nan')))}, {_fmt(s.get('ci_upper', float('nan')))}]"
            _w(
                lines,
                f"| {backend} | {s['n']} | {_fmt(s['mean_ms'])} | {_fmt(s['median_ms'])} "
                f"| {_fmt(s.get('p95', s.get('p95_ms', 0)))} | {ci_str} |",
            )
        _w(lines)


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def generate_report(run_dir: Path) -> str:
    """Generate Phase 2 markdown report (10 sections, fully data-driven)."""
    analysis_path = run_dir / "phase2_analysis.json"
    if not analysis_path.is_file():
        return "# TR126 Phase 2 Report\n\nNo analysis data found.\n"

    data = _load_json(analysis_path)
    manifest = _load_json(run_dir / "manifest.json")
    env = manifest.get("environment", {})
    triton = _load_json(run_dir / "triton_evidence.json")

    lines: list[str] = []

    # === Section 1: Environment ===
    _w(lines, "# TR126 Phase 2: Compile Paradox Replication (Linux + Triton)")
    _w(lines)
    _w(lines, f"*Generated: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}*")
    _w(lines)
    _w(lines, "## 1. Environment")
    _w(lines)
    _w(lines, f"- **Platform:** {env.get('platform', 'N/A')}")
    _w(
        lines,
        f"- **GPU:** {env.get('gpu_name', 'N/A')} ({env.get('gpu_memory_gb', '?')} GB)",
    )
    _w(lines, f"- **PyTorch:** {env.get('torch_version', 'N/A')}")
    _w(lines, f"- **CUDA:** {env.get('cuda_version', 'N/A')}")
    _w(lines, f"- **cuDNN:** {env.get('cudnn_version', 'N/A')}")
    _w(
        lines,
        f"- **Triton:** {triton.get('triton_version', 'N/A')} "
        f"(available: {triton.get('triton_available', False)})",
    )
    _w(lines, f"- **Cached kernels:** {triton.get('cached_kernels', 0)}")
    _w(lines, f"- **In Docker:** {env.get('in_docker', False)}")
    _w(lines)

    # === Section 2: Methodology ===
    _w(lines, "## 2. Methodology")
    _w(lines)
    _w(
        lines,
        "This phase replicates TR120's compile paradox experiment on Linux with real",
    )
    _w(lines, "Inductor+Triton compilation (TR120 Windows fell back to `aot_eager`).")
    _w(lines)
    _w(lines, f"- **Backends:** {', '.join(manifest.get('backends', ['N/A']))}")
    models_raw = manifest.get("models", ["N/A"])
    model_strs = (
        [f"{m['path']}({m.get('dtype', '?')})" for m in models_raw]
        if models_raw and isinstance(models_raw[0], dict)
        else [str(m) for m in models_raw]
    )
    _w(lines, f"- **Models:** {', '.join(model_strs)}")
    _w(lines, f"- **Scenarios:** {', '.join(manifest.get('scenarios', ['N/A']))}")
    _w(lines, f"- **Modes:** {', '.join(manifest.get('modes', ['N/A']))}")
    _w(lines, f"- **Repetitions:** {manifest.get('repetitions', 'N/A')}")
    _w(lines, f"- **Max new tokens:** {manifest.get('max_new_tokens', 'N/A')}")
    _w(lines)
    _w(
        lines,
        "**Key change from TR120:** `fallback_backend` removed — if Triton compilation",
    )
    _w(lines, "fails, the experiment fails. No silent degradation to `aot_eager`.")
    _w(lines)

    # === Section 3: Cross-Phase Validation ===
    xphase = data.get("cross_phase_validation", {})
    _w(lines, "## 3. Cross-Phase Validation")
    _w(lines)
    if xphase.get("validated"):
        status = "PASS" if xphase.get("phase1_pass") else "FAIL"
        _w(lines, f"Phase 1 environment gate: **{status}**")
        _w(lines)
        _w(lines, f"- CUDA: {'OK' if xphase.get('cuda_ok') else 'FAIL'}")
        _w(
            lines,
            f"- Triton: {'OK' if xphase.get('triton_ok') else 'FAIL'} "
            f"(v{xphase.get('triton_version', 'N/A')})",
        )
        _w(
            lines,
            f"- torch.compile inductor: {'OK' if xphase.get('compile_ok') else 'FAIL'}",
        )
        _w(lines, f"- GPU: {xphase.get('gpu_name', 'N/A')}")
        if not xphase.get("phase1_pass"):
            _w(lines)
            _w(
                lines,
                "> **WARNING:** Phase 1 gate did not pass. Phase 2 results may reflect",
            )
            _w(
                lines,
                "> fallback compilation, not real Triton. Interpret with caution.",
            )
    else:
        _w(
            lines,
            f"Phase 1 results not found ({xphase.get('detail', 'unknown reason')}).",
        )
        _w(lines, "Cannot confirm Triton was active during Phase 2.")
    _w(lines)

    # Track all modes for conclusions
    mode_findings: list[dict[str, Any]] = []
    all_pairwise_sig = 0
    all_pairwise_total = 0
    total_outlier_pct: list[float] = []
    section_num = 4

    # === Per-mode sections ===
    for mode in ["prefill", "kv_decode", "e2e_kv"]:
        mode_data = data.get(mode)
        if not mode_data:
            continue

        mode_label = mode.replace("_", " ").title()
        _w(lines, f"## {section_num}. {mode_label} Results")
        _w(lines)
        _w(lines, f"Total samples: {mode_data['n_total']}")
        _w(lines)

        # Backend summary table
        by_backend = mode_data.get("by_backend", {})
        if by_backend:
            _w(lines, f"### {section_num}.1 Backend Summary")
            _w(lines)
            _w(
                lines,
                "| Backend | N | Mean (ms) | Median (ms) | p95 (ms) | p99 (ms) | Std (ms) | 95% CI |",
            )
            _w(
                lines,
                "|---------|---|-----------|-------------|----------|----------|----------|--------|",
            )
            for backend, s in sorted(by_backend.items()):
                ci_str = f"[{_fmt(s.get('ci_lower', float('nan')))}, {_fmt(s.get('ci_upper', float('nan')))}]"
                _w(
                    lines,
                    f"| {backend} | {s['n']} | {_fmt(s['mean_ms'])} | {_fmt(s['median_ms'])} "
                    f"| {_fmt(s.get('p95', s.get('p95_ms', 0)))} "
                    f"| {_fmt(s.get('p99', s.get('p99_ms', 0)))} "
                    f"| {_fmt(s['std_ms'])} | {ci_str} |",
                )
            _w(lines)

        # Per-model breakdown
        _render_model_breakdown(
            lines,
            mode_data.get("by_model_backend", {}),
            f"{section_num}.2",
        )

        # Compile paradox assessment
        cp_list = mode_data.get("compile_paradox", [])
        if isinstance(cp_list, dict):
            cp_list = [cp_list]

        agg_cp = next((c for c in cp_list if c.get("label") == "aggregate"), None)
        scenario_cps = [
            c for c in cp_list if c.get("label") != "aggregate" and not c.get("skipped")
        ]

        subsection = 3 if mode_data.get("by_model_backend") else 2
        if agg_cp and not agg_cp.get("skipped"):
            helps = "helps" if agg_cp["compile_helps_mean"] else "hurts"
            sig = "significant" if agg_cp.get("significant") else "not significant"
            _w(lines, f"### {section_num}.{subsection} Compile Paradox Assessment")
            _w(lines)
            _w(
                lines,
                f"**Aggregate:** compile {helps} "
                f"({agg_cp['mean_delta_pct']:+.1f}%, {sig}, "
                f"d={_fmt(agg_cp.get('cohens_d', 0))} [{_effect_label(agg_cp.get('cohens_d', 0))}])",
            )
            _w(lines)
            _w(
                lines,
                f"- Eager mean: {_fmt(agg_cp['eager_mean'])} ms | "
                f"Compile mean: {_fmt(agg_cp['compile_mean'])} ms",
            )
            _w(
                lines,
                f"- Eager median: {_fmt(agg_cp['eager_median'])} ms | "
                f"Compile median: {_fmt(agg_cp['compile_median'])} ms",
            )
            _w(
                lines,
                f"- t={_fmt(agg_cp.get('t_statistic', float('nan')), 2)}, "
                f"p={_fmt(agg_cp.get('p_value', float('nan')), 4)}",
            )
            _w(lines)

            mode_findings.append(
                {
                    "mode": mode,
                    "helps": agg_cp["compile_helps_mean"],
                    "delta_pct": agg_cp["mean_delta_pct"],
                    "significant": agg_cp.get("significant", False),
                    "cohens_d": agg_cp.get("cohens_d", 0),
                    "n_scenarios_tested": len(scenario_cps),
                    "n_scenarios_consistent": sum(
                        1
                        for sc in scenario_cps
                        if sc.get("compile_helps_mean") == agg_cp["compile_helps_mean"]
                    ),
                }
            )

            # Per-scenario breakdown table
            if scenario_cps:
                _w(lines, "**Per-scenario breakdown:**")
                _w(lines)
                _w(
                    lines,
                    "| Scenario | Compile Helps? | Delta (%) | p-value | Cohen's d | Effect | Sig? |",
                )
                _w(
                    lines,
                    "|----------|---------------|-----------|---------|-----------|--------|------|",
                )
                for sc in scenario_cps:
                    helps_s = "Yes" if sc.get("compile_helps_mean") else "No"
                    sig_s = "Yes" if sc.get("significant") else "No"
                    d_val = sc.get("cohens_d", 0)
                    _w(
                        lines,
                        f"| {sc['label']} | {helps_s} | {sc.get('mean_delta_pct', 0):+.1f}% "
                        f"| {_fmt(sc.get('p_value', float('nan')), 4)} "
                        f"| {_fmt(d_val)} | {_effect_label(d_val)} | {sig_s} |",
                    )
                _w(lines)

            subsection += 1

        # Pairwise comparisons
        pairwise = mode_data.get("pairwise_comparisons", [])
        if pairwise:
            n_sig = sum(1 for pw in pairwise if pw.get("significant"))
            all_pairwise_sig += n_sig
            all_pairwise_total += len(pairwise)
            _w(
                lines,
                f"### {section_num}.{subsection} Pairwise Comparisons "
                f"({n_sig}/{len(pairwise)} significant)",
            )
            _w(lines)
            _w(
                lines,
                "| Group A | Group B | Mean A (ms) | Mean B (ms) | Delta (%) | "
                "t-stat | p-value | Cohen's d | Effect | Sig? |",
            )
            _w(
                lines,
                "|---------|---------|-------------|-------------|-----------|"
                "--------|---------|-----------|--------|------|",
            )
            for pw in pairwise:
                sig_s = "Yes" if pw.get("significant") else "No"
                d_val = pw.get("cohens_d", 0)
                _w(
                    lines,
                    f"| {pw['group_a']} | {pw['group_b']} "
                    f"| {_fmt(pw['mean_a'])} | {_fmt(pw['mean_b'])} "
                    f"| {pw.get('percent_change', 0):+.1f}% "
                    f"| {_fmt(pw.get('t_statistic', 0), 2)} "
                    f"| {_fmt(pw.get('p_value', 1), 4)} "
                    f"| {_fmt(d_val)} | {_effect_label(d_val)} | {sig_s} |",
                )
            _w(lines)
            subsection += 1

        # Outliers
        outliers = mode_data.get("outliers", {})
        if outliers:
            _w(lines, f"### {section_num}.{subsection} Outlier Analysis (IQR)")
            _w(lines)
            _w(lines, "| Backend | N Total | N Outliers | Outlier % |")
            _w(lines, "|---------|---------|------------|-----------|")
            for backend, od in sorted(outliers.items()):
                _w(
                    lines,
                    f"| {backend} | {od['n_total']} | {od['n_outliers']} | {od['outlier_pct']}% |",
                )
                total_outlier_pct.append(od["outlier_pct"])
            _w(lines)
            subsection += 1

        # Cross-platform comparison
        xplat = mode_data.get("cross_platform")
        if xplat:
            _w(
                lines,
                f"### {section_num}.{subsection} Cross-Platform (Linux vs Windows)",
            )
            _w(lines)
            _w(
                lines,
                "| Scenario | Backend | Mean Delta (ms) | Mean Delta (%) | Cohen's d | p-value |",
            )
            _w(
                lines,
                "|----------|---------|-----------------|----------------|-----------|---------|",
            )
            for row in xplat:
                _w(
                    lines,
                    f"| {row.get('scenario', '')} | {row.get('backend', '')} "
                    f"| {_fmt(row.get('mean_delta_ms', 0))} | {row.get('mean_delta_pct', 0):+.1f}% "
                    f"| {_fmt(row.get('cohens_d', 0))} | {_fmt(row.get('mann_whitney_p', 1), 4)} |",
                )
            _w(lines)

        section_num += 1

    # === Power analysis section ===
    _w(lines, f"## {section_num}. Power Analysis")
    _w(lines)
    for mode in ["prefill", "kv_decode", "e2e_kv"]:
        mode_data = data.get(mode, {})
        pa = mode_data.get("power_analysis", {})
        if pa:
            _w(
                lines,
                f"- **{mode}:** N={pa.get('n_per_group', '?')}/group, "
                f"min detectable d={_fmt(pa.get('min_detectable_d', float('nan')))} "
                f"({_fmt(pa.get('min_detectable_ms', float('nan')))} ms), "
                f"{pa.get('interpretation', 'N/A')}",
            )
    _w(lines)
    section_num += 1

    # === Data-driven findings ===
    _w(lines, f"## {section_num}. Findings")
    _w(lines)

    if not mode_findings:
        _w(lines, "No compile paradox data available.")
        _w(lines)
    else:
        finding_num = 1

        # Finding: Compile effect direction
        n_helps = sum(1 for f in mode_findings if f["helps"])
        n_hurts = len(mode_findings) - n_helps
        n_sig = sum(1 for f in mode_findings if f["significant"])
        _w(
            lines,
            f"**Finding {finding_num}:** Compile effect observed in {len(mode_findings)} modes: "
            f"{n_helps} help, {n_hurts} hurt, {n_sig} statistically significant (p<0.05).",
        )
        _w(lines)
        finding_num += 1

        # Finding: Per-mode details
        for f in mode_findings:
            verdict = "helps" if f["helps"] else "hurts"
            sig = "significant" if f["significant"] else "not significant"
            d_label = _effect_label(f["cohens_d"])
            consistency = ""
            if f["n_scenarios_tested"] > 0:
                consistency = (
                    f" ({f['n_scenarios_consistent']}/{f['n_scenarios_tested']} "
                    f"scenarios consistent)"
                )
            _w(
                lines,
                f"**Finding {finding_num}:** {f['mode']}: compile {verdict} "
                f"({f['delta_pct']:+.1f}%, d={_fmt(f['cohens_d'])} [{d_label}], {sig}){consistency}",
            )
            _w(lines)
            finding_num += 1

        # Finding: Scenario consistency
        inconsistent = [
            f
            for f in mode_findings
            if f["n_scenarios_tested"] > 0
            and f["n_scenarios_consistent"] < f["n_scenarios_tested"]
        ]
        if inconsistent:
            _w(
                lines,
                f"**Finding {finding_num}:** Scenario inconsistency detected in "
                f"{len(inconsistent)} mode(s) — compile effect direction varies by scenario, "
                f"suggesting input-length sensitivity.",
            )
            _w(lines)
            finding_num += 1

        # Finding: Pairwise significance rate
        if all_pairwise_total > 0:
            sig_pct = 100 * all_pairwise_sig / all_pairwise_total
            _w(
                lines,
                f"**Finding {finding_num}:** {all_pairwise_sig}/{all_pairwise_total} "
                f"({sig_pct:.0f}%) pairwise comparisons reached significance.",
            )
            _w(lines)
            finding_num += 1

        # Finding: Outlier burden
        if total_outlier_pct:
            mean_outlier = sum(total_outlier_pct) / len(total_outlier_pct)
            max_outlier = max(total_outlier_pct)
            _w(
                lines,
                f"**Finding {finding_num}:** Mean outlier rate: {mean_outlier:.1f}%, "
                f"max: {max_outlier:.1f}% (IQR method).",
            )
            _w(lines)
            finding_num += 1

    section_num += 1

    # === Conclusions ===
    _w(lines, f"## {section_num}. Conclusions & Implications")
    _w(lines)

    if mode_findings:
        all_help = all(f["helps"] for f in mode_findings)
        none_help = not any(f["helps"] for f in mode_findings)
        any_significant = any(f["significant"] for f in mode_findings)
        all_large = all(abs(f["cohens_d"]) >= 0.8 for f in mode_findings)

        if all_help and any_significant:
            _w(
                lines,
                "1. **Compile paradox resolved:** Real Triton compilation consistently",
            )
            _w(
                lines,
                "   helps across all measured modes. The TR120 paradox was caused by",
            )
            _w(
                lines,
                "   the `aot_eager` fallback on Windows, not by `torch.compile` itself.",
            )
        elif none_help and any_significant:
            _w(
                lines,
                "1. **Compile paradox persists:** Even with real Triton, compilation",
            )
            _w(
                lines,
                "   hurts performance. The overhead is inherent to the model/scenario",
            )
            _w(lines, "   combination, not caused by the Windows fallback.")
        else:
            _w(
                lines,
                "1. **Mixed compile effect:** The compile paradox outcome depends on mode:",
            )
            for f in mode_findings:
                verdict = (
                    "resolved (compile helps)"
                    if f["helps"]
                    else "persists (compile hurts)"
                )
                _w(lines, f"   - {f['mode']}: {verdict}")

        _w(lines)

        if all_large:
            _w(
                lines,
                "2. **Large effect sizes** across all modes — differences are practically",
            )
            _w(lines, "   meaningful, not just statistically significant.")
        elif any_significant:
            effects = {_effect_label(f["cohens_d"]) for f in mode_findings}
            _w(
                lines,
                f"2. **Effect sizes range**: {', '.join(sorted(effects))} — "
                f"consider practical significance alongside p-values.",
            )
        _w(lines)

        if inconsistent:
            _w(
                lines,
                "3. **Scenario sensitivity:** Compile effect varies by input length in some",
            )
            _w(
                lines,
                "   modes. Production workloads with mixed prompt lengths may see inconsistent",
            )
            _w(lines, "   benefits from `torch.compile`.")
            _w(lines)

    _w(lines)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="TR126 Phase 2 report generation")
    parser.add_argument("--results-dir", type=Path, default=None)
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable debug logging"
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    results_root = _REPO / "research" / "tr126" / "results" / "phase2"
    if args.results_dir:
        run_dir = Path(args.results_dir)
    else:
        run_dir = find_latest_run(results_root)
        if run_dir is None:
            logger.error("No Phase 2 results found.")
            return 1

    report = generate_report(run_dir)
    out_path = run_dir / "phase2_report.md"
    out_path.write_text(report, encoding="utf-8")
    logger.info("Report written: %s (%d lines)", out_path, len(report.splitlines()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
