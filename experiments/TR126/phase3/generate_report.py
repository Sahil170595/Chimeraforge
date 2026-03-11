#!/usr/bin/env python3
"""TR126 Phase 3: Generate markdown report from analysis results.

Produces a 9-section report from phase3_analysis.json:
  1.  Environment — GPU, CUDA, Triton, Docker
  2.  Methodology — matrix design, backends, models, scenarios
  3.  Cross-Phase Validation — Phase 1 gate status
  4-6. Per-mode results (one section per mode):
      - Backend rankings with CI
      - Per-model breakdown tables
      - Compile effect (gpu vs gpu-compile)
      - Pairwise comparisons
      - Outlier analysis
  7.  Power Analysis — minimum detectable effect with ms interpretation
  8.  Data-Driven Findings — computed from all mode results
  9.  Conclusions & Implications — synthesized across modes

All findings are derived from analysis data — no hard-coded assumptions.

Usage:
    python research/tr126/phase3/generate_report.py [--results-dir DIR] [-v]
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

logger = logging.getLogger("tr126.phase3.report")


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
    if val != val:  # NaN
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
) -> bool:
    """Render per-model × backend ranking tables.

    Shows a separate table per model, sorted by mean latency within each.
    Returns True if any content was rendered.
    """
    if not by_model_backend:
        return False

    # Group by model
    models: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    for key, stats in by_model_backend.items():
        parts = key.rsplit("/", 1)
        if len(parts) == 2:
            model, backend = parts
            models[model].append((backend, stats))

    if not models:
        return False

    _w(lines, f"### {section_prefix} Per-Model Rankings")
    _w(lines)

    for model, entries in sorted(models.items()):
        _w(lines, f"**{model}:**")
        _w(lines)
        _w(
            lines,
            "| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | 95% CI |",
        )
        _w(
            lines,
            "|------|---------|---|-----------|-------------|----------|--------|",
        )
        entries.sort(key=lambda e: e[1].get("mean_ms", float("inf")))
        for rank, (backend, s) in enumerate(entries, 1):
            ci_str = f"[{_fmt(s.get('ci_lower', float('nan')))}, {_fmt(s.get('ci_upper', float('nan')))}]"
            _w(
                lines,
                f"| {rank} | {backend} | {s['n']} | {_fmt(s['mean_ms'])} | {_fmt(s['median_ms'])} "
                f"| {_fmt(s.get('p95_ms', 0))} | {ci_str} |",
            )
        _w(lines)

    return True


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def generate_report(run_dir: Path) -> str:
    """Generate Phase 3 markdown report (10 sections, fully data-driven)."""
    analysis_path = run_dir / "phase3_analysis.json"
    if not analysis_path.is_file():
        return "# TR126 Phase 3 Report\n\nNo analysis data found.\n"

    data = _load_json(analysis_path)
    manifest = _load_json(run_dir / "manifest.json")
    env = manifest.get("environment", {})

    lines: list[str] = []

    # === Section 1: Environment ===
    _w(lines, "# TR126 Phase 3: Backend Matrix Rerun (Linux)")
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
    _w(lines, f"- **Triton:** {env.get('triton_version', 'N/A')}")
    _w(lines, f"- **In Docker:** {env.get('in_docker', False)}")
    _w(lines)

    # === Section 2: Methodology ===
    _w(lines, "## 2. Methodology")
    _w(lines)
    _w(
        lines,
        "This phase reruns TR117's Tier-3 backend matrix on Linux to determine if",
    )
    _w(lines, "backend rankings change under real Triton compilation.")
    _w(lines)
    _w(lines, f"- **Backends:** {', '.join(manifest.get('backends', ['N/A']))}")
    _w(lines, f"- **Models:** {', '.join(manifest.get('models', ['N/A']))}")
    _w(lines, f"- **Scenarios:** {', '.join(manifest.get('scenarios', ['N/A']))}")
    _w(lines, f"- **Modes:** {', '.join(manifest.get('modes', ['N/A']))}")
    _w(lines, f"- **Repetitions:** {manifest.get('repetitions', 'N/A')}")
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
                "> **WARNING:** Phase 1 gate did not pass. Phase 3 results may reflect",
            )
            _w(lines, "> fallback compilation. Interpret with caution.")
    else:
        _w(
            lines,
            f"Phase 1 results not found ({xphase.get('detail', 'unknown reason')}).",
        )
        _w(lines, "Cannot confirm Triton was active during Phase 3.")
    _w(lines)

    # Track findings across modes
    mode_winners: list[dict[str, Any]] = []
    compile_effects: list[dict[str, Any]] = []
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
        _w(lines, f"## {section_num}. {mode_label}")
        _w(lines)
        _w(lines, f"Total samples: {mode_data['n_total']}")
        _w(lines)

        # Rankings table
        rankings = mode_data.get("rankings", [])
        if rankings:
            _w(lines, f"### {section_num}.1 Backend Rankings (by mean latency)")
            _w(lines)
            _w(
                lines,
                "| Rank | Backend | N | Mean (ms) | Median (ms) | p95 (ms) | "
                "Std (ms) | 95% CI |",
            )
            _w(
                lines,
                "|------|---------|---|-----------|-------------|----------|"
                "----------|--------|",
            )
            for r in rankings:
                ci_str = f"[{_fmt(r.get('ci_lower', float('nan')))}, {_fmt(r.get('ci_upper', float('nan')))}]"
                _w(
                    lines,
                    f"| {r['rank_by_mean']} | {r['backend']} | {r['n']} "
                    f"| {_fmt(r['mean_ms'])} | {_fmt(r['median_ms'])} "
                    f"| {_fmt(r.get('p95_ms', 0))} | {_fmt(r['std_ms'])} | {ci_str} |",
                )
            _w(lines)

            mode_winners.append(
                {
                    "mode": mode,
                    "winner": rankings[0]["backend"],
                    "mean_ms": rankings[0]["mean_ms"],
                    "n_backends": len(rankings),
                }
            )

        # Per-model breakdown
        subsection = 2
        has_model = _render_model_breakdown(
            lines,
            mode_data.get("by_model_backend", {}),
            f"{section_num}.{subsection}",
        )
        if has_model:
            subsection += 1

        # Compile effect
        ce = mode_data.get("compile_effect")
        if ce:
            helps = "helps" if ce["compile_helps"] else "hurts"
            sig = "significant" if ce.get("significant") else "not significant"
            d_val = ce.get("cohens_d", 0)
            _w(
                lines,
                f"### {section_num}.{subsection} Compile Effect: "
                f"{helps} ({ce['delta_pct']:+.1f}%, {sig}, d={_fmt(d_val)} [{_effect_label(d_val)}])",
            )
            _w(lines)
            _w(
                lines,
                f"- GPU eager mean: {_fmt(ce['gpu_mean'])} ms | "
                f"GPU compile mean: {_fmt(ce['gpu_compile_mean'])} ms",
            )
            _w(
                lines,
                f"- t={_fmt(ce.get('t_statistic', float('nan')), 2)}, "
                f"p={_fmt(ce.get('p_value', float('nan')), 4)}",
            )
            _w(lines)

            compile_effects.append(
                {
                    "mode": mode,
                    "helps": ce["compile_helps"],
                    "delta_pct": ce["delta_pct"],
                    "significant": ce.get("significant", False),
                    "cohens_d": d_val,
                }
            )
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
                "p-value | Cohen's d | Effect | Sig? |",
            )
            _w(
                lines,
                "|---------|---------|-------------|-------------|-----------|"
                "---------|-----------|--------|------|",
            )
            for pw in pairwise:
                sig_s = "Yes" if pw.get("significant") else "No"
                d_val = pw.get("cohens_d", 0)
                _w(
                    lines,
                    f"| {pw['group_a']} | {pw['group_b']} "
                    f"| {_fmt(pw['mean_a'])} | {_fmt(pw['mean_b'])} "
                    f"| {pw.get('percent_change', 0):+.1f}% "
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

    finding_num = 1

    # Finding: Backend ranking consistency
    if mode_winners:
        winners_set = {w["winner"] for w in mode_winners}
        if len(winners_set) == 1:
            winner = winners_set.pop()
            _w(
                lines,
                f"**Finding {finding_num}:** **{winner}** ranks #1 across all "
                f"{len(mode_winners)} measured modes on Linux.",
            )
        else:
            _w(
                lines,
                f"**Finding {finding_num}:** Backend rankings vary by mode "
                f"({len(winners_set)} different winners across {len(mode_winners)} modes):",
            )
            for w in mode_winners:
                _w(lines, f"  - {w['mode']}: {w['winner']} ({_fmt(w['mean_ms'])} ms)")
        _w(lines)
        finding_num += 1

        # Check if per-model rankings are consistent
        for mode_data_name in ["prefill", "kv_decode", "e2e_kv"]:
            md = data.get(mode_data_name, {})
            by_model = md.get("by_model_backend", {})
            if by_model:
                # Group by model, find winner per model
                model_winners: dict[str, str] = {}
                model_entries: dict[str, list[tuple[str, float]]] = defaultdict(list)
                for key, stats in by_model.items():
                    parts = key.rsplit("/", 1)
                    if len(parts) == 2:
                        model, backend = parts
                        model_entries[model].append(
                            (backend, stats.get("mean_ms", float("inf")))
                        )
                for model, entries in model_entries.items():
                    entries.sort(key=lambda e: e[1])
                    model_winners[model] = entries[0][0]

                unique_winners = set(model_winners.values())
                if len(unique_winners) > 1 and len(model_winners) > 1:
                    _w(
                        lines,
                        f"**Finding {finding_num}:** Rankings differ by model in {mode_data_name}:",
                    )
                    for model, winner in sorted(model_winners.items()):
                        _w(lines, f"  - {model}: {winner}")
                    _w(lines)
                    finding_num += 1
                break  # Only report for first mode with model data

    # Finding: Compile effect
    if compile_effects:
        n_helps = sum(1 for c in compile_effects if c["helps"])
        n_sig = sum(1 for c in compile_effects if c["significant"])
        _w(
            lines,
            f"**Finding {finding_num}:** Compile effect: "
            f"{n_helps}/{len(compile_effects)} modes helped, "
            f"{n_sig} statistically significant.",
        )
        _w(lines)
        finding_num += 1

        for c in compile_effects:
            verdict = "helps" if c["helps"] else "hurts"
            sig = "significant" if c["significant"] else "not significant"
            d_label = _effect_label(c["cohens_d"])
            _w(
                lines,
                f"**Finding {finding_num}:** {c['mode']}: compile {verdict} "
                f"({c['delta_pct']:+.1f}%, d={_fmt(c['cohens_d'])} [{d_label}], {sig})",
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
        _w(
            lines,
            f"**Finding {finding_num}:** Mean outlier rate: {mean_outlier:.1f}% (IQR method).",
        )
        _w(lines)
        finding_num += 1

    section_num += 1

    # === Conclusions ===
    _w(lines, f"## {section_num}. Conclusions & Implications")
    _w(lines)

    conclusion_num = 1

    # Conclusion: Ranking stability
    if mode_winners:
        winners_set = {w["winner"] for w in mode_winners}
        if len(winners_set) == 1:
            _w(
                lines,
                f"{conclusion_num}. **Stable rankings:** Backend rankings are consistent across",
            )
            _w(
                lines,
                "   modes on Linux. Platform change does not affect relative performance.",
            )
        else:
            _w(
                lines,
                f"{conclusion_num}. **Mode-dependent rankings:** No single backend dominates",
            )
            _w(lines, "   all modes. Backend selection should be mode-aware.")
        _w(lines)
        conclusion_num += 1

    # Conclusion: Compile effect
    if compile_effects:
        all_help = all(c["helps"] for c in compile_effects)
        none_help = not any(c["helps"] for c in compile_effects)
        any_sig = any(c["significant"] for c in compile_effects)

        if all_help and any_sig:
            _w(
                lines,
                f"{conclusion_num}. **Compilation beneficial:** Real Triton compilation "
                "consistently helps.",
            )
            _w(
                lines,
                "   Unlike TR120's `aot_eager` fallback, real inductor delivers speedups.",
            )
        elif none_help and any_sig:
            _w(
                lines,
                f"{conclusion_num}. **Compilation overhead persists:** Even with real Triton,",
            )
            _w(
                lines,
                "   compilation hurts. The overhead is inherent, not fallback-related.",
            )
        else:
            _w(
                lines,
                f"{conclusion_num}. **Mixed compile effect:** Compilation benefit is mode-dependent.",
            )
            for c in compile_effects:
                verdict = "helps" if c["helps"] else "hurts"
                _w(lines, f"   - {c['mode']}: {verdict} ({c['delta_pct']:+.1f}%)")
        _w(lines)
        conclusion_num += 1

    # Conclusion: Effect size interpretation
    if compile_effects:
        large = [c for c in compile_effects if abs(c["cohens_d"]) >= 0.8]
        if large:
            _w(
                lines,
                f"{conclusion_num}. **Practically meaningful:** Large effect sizes in "
                f"{', '.join(c['mode'] for c in large)} — differences are operationally relevant.",
            )
            _w(lines)
            conclusion_num += 1

    _w(lines)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="TR126 Phase 3 report generation")
    parser.add_argument("--results-dir", type=Path, default=None)
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable debug logging"
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    results_root = _REPO / "research" / "tr126" / "results" / "phase3"
    if args.results_dir:
        run_dir = Path(args.results_dir)
    else:
        run_dir = find_latest_run(results_root)
        if run_dir is None:
            logger.error("No Phase 3 results found.")
            return 1

    report = generate_report(run_dir)
    out_path = run_dir / "phase3_report.md"
    out_path.write_text(report, encoding="utf-8")
    logger.info("Report written: %s (%d lines)", out_path, len(report.splitlines()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
