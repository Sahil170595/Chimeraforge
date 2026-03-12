"""TR133 -- CLI Capacity Planner.

Recommends optimal model + quantization + backend configuration
for a given deployment scenario by searching the solution space
and filtering through VRAM, quality, latency, and budget gates.

Usage:
    python -m research.tr133.plan \\
        --model-size 3b \\
        --request-rate 2 \\
        --latency-slo 500 \\
        --quality-target 0.6 \\
        --budget 50 \\
        --hardware "RTX 4080 12GB"

    python -m research.tr133.plan --list-hardware
    python -m research.tr133.plan --list-models
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import logging
from pathlib import Path
import sys

_DIR = Path(__file__).resolve().parent
_REPO = _DIR.parents[1]
sys.path.insert(0, str(_REPO))

from research.tr133.shared.hardware_db import GPU_DB, get_gpu
from research.tr133.shared.models import PlannerModels, load_models
from research.tr133.shared.utils import (
    BACKENDS,
    MODEL_PARAMS_B,
    QUANT_BPW,
    QUANT_LEVELS,
    TR133_RESULTS,
    find_latest_run,
)

log = logging.getLogger("tr133.plan")


@dataclass
class Candidate:
    model: str
    quant: str
    backend: str
    n_agents: int
    vram_gb: float
    quality: float
    quality_tier: str
    throughput_tps: float
    total_throughput_tps: float
    eta: float
    p95_latency_ms: float
    utilisation: float
    monthly_cost: float
    cost_per_1m_tok: float
    warnings: list[str]


def _find_models_for_size(target_size: str) -> list[str]:
    """Map size class (1b, 3b, 8b, etc.) to available models."""
    target = target_size.lower().replace("b", "")
    try:
        target_val = float(target)
    except ValueError:
        return list(MODEL_PARAMS_B.keys())

    matches = []
    for model, params in MODEL_PARAMS_B.items():
        if abs(params - target_val) / target_val < 0.5:
            matches.append(model)

    if not matches:
        # Return closest
        closest = min(MODEL_PARAMS_B, key=lambda m: abs(MODEL_PARAMS_B[m] - target_val))
        matches = [closest]

    return matches


def _enumerate_candidates(
    models: PlannerModels,
    target_models: list[str],
    hardware: str,
    request_rate: float,
    latency_slo: float,
    quality_target: float,
    budget: float,
    avg_tokens: int,
    context_length: int,
) -> list[Candidate]:
    """Search (model, quant, backend, N) space with 4 gates."""
    gpu = get_gpu(hardware)
    hw_vram = gpu.vram_gb if gpu else 12.0
    hw_cost_hr = gpu.cost_per_hour if gpu else 0.035

    candidates: list[Candidate] = []

    for model in target_models:
        for quant in QUANT_LEVELS:
            # ── Gate 1: VRAM ──
            vram = models.vram.predict(model, quant, context_length)
            if vram > hw_vram:
                continue

            # ── Gate 2: Quality ──
            quality = models.quality.predict(model, quant)
            if quality < quality_target:
                continue

            quality_tier = models.quality.quality_tier(model, quant)

            for backend in BACKENDS:
                # ── Predict N=1 throughput ──
                n1_tps = models.throughput.predict(
                    model,
                    backend,
                    quant,
                    hardware,
                )

                # ── Find minimum N to meet request_rate ──
                # Each request generates ~avg_tokens tokens
                # Required total tok/s = request_rate * avg_tokens
                required_tps = request_rate * avg_tokens

                best_n = None
                for n in range(1, 17):
                    eta = models.scaling.predict_eta(model, backend, n)
                    total_tps = n * n1_tps * eta
                    if total_tps >= required_tps:
                        best_n = n
                        break

                if best_n is None:
                    # Even N=16 can't meet the request rate
                    continue

                eta = models.scaling.predict_eta(model, backend, best_n)
                total_tps = best_n * n1_tps * eta

                # ── Gate 3: Latency ──
                lat = models.latency.predict_p95(
                    model,
                    backend,
                    request_rate,
                    n_agents=best_n,
                    avg_tokens=avg_tokens,
                    quant=quant,
                    throughput_model=models.throughput,
                    scaling_model=models.scaling,
                    hardware=hardware,
                )
                if lat["p95_ms"] > latency_slo:
                    continue

                # ── Gate 4: Cost ──
                monthly = models.cost.predict_monthly(hw_cost_hr) * best_n
                if monthly > budget:
                    continue

                cost_1m = models.cost.predict_cost_per_1m(total_tps, hw_cost_hr)

                # Warnings
                warnings = []
                if lat["saturated"]:
                    warnings.append("utilisation > 70% safety cap")
                if quality_tier == "concerning":
                    warnings.append("quality drop concerning (-10 to -15pp)")
                if best_n > 8:
                    warnings.append(f"requires {best_n} GPU instances")
                if vram / hw_vram > 0.9:
                    warnings.append("VRAM usage > 90% of capacity")

                candidates.append(
                    Candidate(
                        model=model,
                        quant=quant,
                        backend=backend,
                        n_agents=best_n,
                        vram_gb=round(vram, 2),
                        quality=round(quality, 3),
                        quality_tier=quality_tier,
                        throughput_tps=round(n1_tps, 1),
                        total_throughput_tps=round(total_tps, 1),
                        eta=round(eta, 3),
                        p95_latency_ms=round(lat["p95_ms"], 1),
                        utilisation=round(lat["utilisation"], 3),
                        monthly_cost=round(monthly, 2),
                        cost_per_1m_tok=round(cost_1m, 4),
                        warnings=warnings,
                    )
                )

    # Sort by monthly cost (primary), then by quality (secondary, desc)
    candidates.sort(key=lambda c: (c.monthly_cost, -c.quality))
    return candidates


def _format_recommendation(
    candidates: list[Candidate],
    hardware: str,
    request_rate: float,
    latency_slo: float,
    quality_target: float,
    budget: float,
) -> str:
    """Format the recommendation as a human-readable report."""
    if not candidates:
        return (
            "No viable configuration found.\n"
            "Try: relaxing quality target, increasing budget, "
            "raising latency SLO, or using a larger GPU."
        )

    lines = []
    best = candidates[0]

    lines.append("=" * 64)
    lines.append("  TR133 CAPACITY PLANNER - RECOMMENDATION")
    lines.append("=" * 64)
    lines.append("")
    lines.append("  Constraints:")
    lines.append(f"    Request rate:     {request_rate} req/s")
    lines.append(f"    Latency SLO:      {latency_slo} ms (p95)")
    lines.append(f"    Quality target:   {quality_target}")
    lines.append(f"    Budget:           ${budget}/mo")
    lines.append(f"    Hardware:         {hardware}")
    lines.append("")
    lines.append("  Best configuration:")
    lines.append(
        f"    Model:      {best.model} ({MODEL_PARAMS_B.get(best.model, '?')}B params)"
    )
    lines.append(
        f"    Quant:      {best.quant} ({QUANT_BPW.get(best.quant, '?')} bits/weight)"
    )
    lines.append(f"    Backend:    {best.backend}")
    lines.append(f"    Instances:  {best.n_agents}")
    lines.append("")
    lines.append("  Performance:")
    lines.append(f"    N=1 throughput:   {best.throughput_tps} tok/s")
    lines.append(f"    Total throughput: {best.total_throughput_tps} tok/s")
    lines.append(f"    Scaling eta(N):   {best.eta}")
    lines.append(f"    p95 latency:      {best.p95_latency_ms} ms")
    lines.append(f"    Utilisation:      {best.utilisation:.1%}")
    lines.append("")
    lines.append("  Quality:")
    lines.append(f"    Composite score:  {best.quality}")
    lines.append(f"    Quality tier:     {best.quality_tier}")
    lines.append("")
    lines.append("  Resources:")
    lines.append(f"    VRAM per GPU:     {best.vram_gb} GB")
    lines.append(f"    Monthly cost:     ${best.monthly_cost}")
    lines.append(f"    Cost per 1M tok:  ${best.cost_per_1m_tok}")

    if best.warnings:
        lines.append("")
        lines.append("  Warnings:")
        for w in best.warnings:
            lines.append(f"    - {w}")

    # Alternatives
    alts = candidates[1:5]
    if alts:
        lines.append("")
        lines.append("-" * 64)
        lines.append("  Alternatives (next 4 cheapest):")
        lines.append("-" * 64)
        for i, alt in enumerate(alts, 1):
            lines.append(
                f"  {i}. {alt.model} {alt.quant} / {alt.backend} "
                f"(N={alt.n_agents}) -- ${alt.monthly_cost}/mo, "
                f"q={alt.quality}, p95={alt.p95_latency_ms}ms"
            )

    lines.append("")
    lines.append("-" * 64)
    lines.append(f"  {len(candidates)} total viable configurations evaluated")
    lines.append("=" * 64)
    return "\n".join(lines)


def _format_json(candidates: list[Candidate]) -> str:
    """Format candidates as JSON for programmatic consumption."""
    return json.dumps(
        [
            {
                "model": c.model,
                "quant": c.quant,
                "backend": c.backend,
                "n_agents": c.n_agents,
                "vram_gb": c.vram_gb,
                "quality": c.quality,
                "quality_tier": c.quality_tier,
                "throughput_tps": c.throughput_tps,
                "total_throughput_tps": c.total_throughput_tps,
                "eta": c.eta,
                "p95_latency_ms": c.p95_latency_ms,
                "utilisation": c.utilisation,
                "monthly_cost": c.monthly_cost,
                "cost_per_1m_tok": c.cost_per_1m_tok,
                "warnings": c.warnings,
            }
            for c in candidates
        ],
        indent=2,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="TR133: Predictive Capacity Planner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python -m research.tr133.plan --model-size 3b --request-rate 2\n"
            "  python -m research.tr133.plan --model-size 8b --budget 100 --hardware 'RTX 4090 24GB'\n"
            "  python -m research.tr133.plan --list-hardware\n"
        ),
    )
    parser.add_argument(
        "--model-size", default="3b", help="Target model size class (e.g., 1b, 3b, 8b)"
    )
    parser.add_argument(
        "--request-rate",
        type=float,
        default=1.0,
        help="Requests per second (default: 1.0)",
    )
    parser.add_argument(
        "--latency-slo",
        type=float,
        default=5000.0,
        help="Max p95 latency in ms (default: 5000)",
    )
    parser.add_argument(
        "--quality-target",
        type=float,
        default=0.5,
        help="Min composite quality 0-1 (default: 0.5)",
    )
    parser.add_argument(
        "--budget",
        type=float,
        default=100.0,
        help="Max monthly cost in $ (default: 100)",
    )
    parser.add_argument(
        "--hardware",
        default="RTX 4080 12GB",
        help="GPU name from hardware DB (default: RTX 4080 12GB)",
    )
    parser.add_argument(
        "--context-length",
        type=int,
        default=2048,
        help="Context window length (default: 2048)",
    )
    parser.add_argument(
        "--avg-tokens",
        type=int,
        default=128,
        help="Average output tokens per request (default: 128)",
    )
    parser.add_argument(
        "--models-path", help="Path to fitted_models.json (default: latest run)"
    )
    parser.add_argument(
        "--json", action="store_true", help="Output as JSON instead of human-readable"
    )
    parser.add_argument(
        "--list-hardware",
        action="store_true",
        help="List available GPUs in hardware DB",
    )
    parser.add_argument(
        "--list-models", action="store_true", help="List available model sizes"
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(asctime)s %(name)s %(levelname)s  %(message)s",
    )

    if args.list_hardware:
        print(f"{'GPU':<25} {'VRAM':>6} {'BW GB/s':>8} {'$/hr':>6}")
        print("-" * 50)
        for name, spec in sorted(GPU_DB.items()):
            print(
                f"{name:<25} {spec.vram_gb:>5.0f}G {spec.bandwidth_gbps:>7.0f} {spec.cost_per_hour:>6.3f}"
            )
        return 0

    if args.list_models:
        print(f"{'Model':<20} {'Params (B)':>10}")
        print("-" * 32)
        for name, params in sorted(MODEL_PARAMS_B.items(), key=lambda x: x[1]):
            print(f"{name:<20} {params:>10.2f}")
        return 0

    # Load fitted models
    if args.models_path:
        models_path = Path(args.models_path)
    else:
        run_dir = find_latest_run(TR133_RESULTS)
        if run_dir is None:
            print(
                "Error: No fitted models found. Run `python -m research.tr133.run` first."
            )
            return 1
        models_path = run_dir / "fitted_models.json"

    if not models_path.exists():
        print(f"Error: Models file not found: {models_path}")
        return 1

    planner_models = load_models(models_path)

    # Resolve target models
    target_models = _find_models_for_size(args.model_size)

    # Validate hardware
    gpu = get_gpu(args.hardware)
    if gpu is None:
        print(
            f"Warning: '{args.hardware}' not in hardware DB, using default RTX 4080 12GB specs"
        )

    # Search
    candidates = _enumerate_candidates(
        models=planner_models,
        target_models=target_models,
        hardware=args.hardware,
        request_rate=args.request_rate,
        latency_slo=args.latency_slo,
        quality_target=args.quality_target,
        budget=args.budget,
        avg_tokens=args.avg_tokens,
        context_length=args.context_length,
    )

    if args.json:
        print(_format_json(candidates))
    else:
        print(
            _format_recommendation(
                candidates,
                args.hardware,
                request_rate=args.request_rate,
                latency_slo=args.latency_slo,
                quality_target=args.quality_target,
                budget=args.budget,
            )
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
