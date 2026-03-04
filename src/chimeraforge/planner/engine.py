"""4-gate search engine for capacity planning.

Searches the (model, quant, backend, N) solution space and filters
through VRAM, quality, latency, and budget gates to find viable
deployment configurations.
"""

from __future__ import annotations

from dataclasses import dataclass

from chimeraforge.planner.constants import (
    BACKENDS,
    MODEL_PARAMS_B,
    QUANT_LEVELS,
)
from chimeraforge.planner.hardware import get_gpu
from chimeraforge.planner.models import PlannerModels


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


def find_models_for_size(target_size: str) -> list[str]:
    """Map size class (1b, 3b, 8b, etc.) to available models."""
    target = target_size.lower().replace("b", "")
    try:
        target_val = float(target)
    except ValueError:
        return list(MODEL_PARAMS_B.keys())

    if target_val <= 0:
        return list(MODEL_PARAMS_B.keys())

    matches = []
    for model, params in MODEL_PARAMS_B.items():
        if abs(params - target_val) / target_val < 0.5:
            matches.append(model)

    if not matches:
        closest = min(MODEL_PARAMS_B, key=lambda m: abs(MODEL_PARAMS_B[m] - target_val))
        matches = [closest]

    return matches


def enumerate_candidates(
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
            # Gate 1: VRAM
            vram = models.vram.predict(model, quant, context_length)
            if vram > hw_vram:
                continue

            # Gate 2: Quality
            quality = models.quality.predict(model, quant)
            if quality < quality_target:
                continue

            quality_tier = models.quality.quality_tier(model, quant)

            for backend in BACKENDS:
                # Predict N=1 throughput
                n1_tps = models.throughput.predict(model, backend, quant, hardware)

                # Find minimum N to meet request_rate
                required_tps = request_rate * avg_tokens

                # Find minimum N that satisfies both throughput and latency
                best_n = None
                for n in range(1, 17):
                    eta = models.scaling.predict_eta(model, backend, n)
                    total_tps = n * n1_tps * eta
                    if total_tps < required_tps:
                        continue

                    lat = models.latency.predict_p95(
                        model,
                        backend,
                        request_rate,
                        n_agents=n,
                        avg_tokens=avg_tokens,
                        quant=quant,
                        throughput_model=models.throughput,
                        scaling_model=models.scaling,
                        hardware=hardware,
                    )
                    if lat["p95_ms"] <= latency_slo:
                        best_n = n
                        break

                if best_n is None:
                    continue

                eta = models.scaling.predict_eta(model, backend, best_n)
                total_tps = best_n * n1_tps * eta
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

                # Gate 4: Cost
                monthly = models.cost.predict_monthly(hw_cost_hr) * best_n
                if monthly > budget:
                    continue

                cost_1m = models.cost.predict_cost_per_1m(total_tps, hw_cost_hr)

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
