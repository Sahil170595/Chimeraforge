"""Cost analysis for TR117 backend comparison."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass
class CostProfile:
    """Cost profile for a backend."""

    backend: str
    tokens_per_second: float
    avg_latency_ms: float
    memory_mb_mean: float
    memory_mb_peak: float
    gpu_util_percent_mean: float | None
    gpu_memory_mb_mean: float | None

    # Cost calculations
    cost_per_million_tokens_usd: float
    cost_per_hour_usd: float
    tokens_per_dollar: float

    # Efficiency metrics
    memory_efficiency: float  # tokens/MB
    compute_efficiency: float  # tokens/ms

    # Meta
    n_samples: int


# Pricing assumptions (can be customized)
PRICING = {
    "cpu_core_hour_usd": 0.05,  # AWS c5.large ~ $0.085/hr for 2 vCPU
    "gpu_hour_usd": 1.00,  # AWS g4dn.xlarge ~ $0.526/hr (T4)
    "memory_gb_hour_usd": 0.005,  # Part of instance cost
}


def estimate_cost_per_hour(
    cpu_percent_mean: float,
    memory_gb_mean: float,
    gpu_util_percent_mean: float | None,
    gpu_memory_gb_mean: float | None,
) -> float:
    """Estimate cost per hour based on resource usage."""

    # CPU cost (scale by utilization)
    cpu_cost = PRICING["cpu_core_hour_usd"] * (cpu_percent_mean / 100)

    # Memory cost
    memory_cost = PRICING["memory_gb_hour_usd"] * memory_gb_mean

    # GPU cost (if used)
    gpu_cost = 0.0
    if gpu_util_percent_mean is not None and gpu_util_percent_mean > 0:
        gpu_cost = PRICING["gpu_hour_usd"] * (gpu_util_percent_mean / 100)

    return cpu_cost + memory_cost + gpu_cost


def compute_cost_profile(
    backend: str,
    metrics_df: pd.DataFrame,
    resource_profiles: dict[str, Any] | None = None,
) -> CostProfile:
    """Compute comprehensive cost profile for a backend."""

    # Filter to backend
    backend_data = metrics_df[
        (metrics_df["backend"] == backend) & (metrics_df["status"] == "ok")
    ]

    if len(backend_data) == 0:
        return CostProfile(
            backend=backend,
            tokens_per_second=0.0,
            avg_latency_ms=0.0,
            memory_mb_mean=0.0,
            memory_mb_peak=0.0,
            gpu_util_percent_mean=None,
            gpu_memory_mb_mean=None,
            cost_per_million_tokens_usd=0.0,
            cost_per_hour_usd=0.0,
            tokens_per_dollar=0.0,
            memory_efficiency=0.0,
            compute_efficiency=0.0,
            n_samples=0,
        )

    # Basic metrics
    tokens_per_second = backend_data["tokens_per_s"].mean()
    avg_latency_ms = backend_data["latency_ms"].mean()

    # Resource usage (from resource profiles if available)
    memory_mb_mean = 0.0
    memory_mb_peak = 0.0
    gpu_util_mean = None
    gpu_memory_mb_mean = None

    if resource_profiles and backend in resource_profiles:
        profile = resource_profiles[backend]
        memory_mb_mean = profile.get("memory_mean_mb", 0.0)
        memory_mb_peak = profile.get("memory_max_mb", 0.0)
        gpu_util_mean = profile.get("gpu_util_mean_percent")
        gpu_memory_mb_mean = profile.get("gpu_memory_mean_mb")

    # Cost estimation
    cpu_percent_mean = 50.0  # Assume 50% CPU if no data
    memory_gb_mean = (
        memory_mb_mean / 1024 if memory_mb_mean > 0 else 2.0
    )  # Assume 2GB if no data
    gpu_util_percent_mean = gpu_util_mean if gpu_util_mean else None
    gpu_memory_gb_mean = gpu_memory_mb_mean / 1024 if gpu_memory_mb_mean else None

    cost_per_hour = estimate_cost_per_hour(
        cpu_percent_mean, memory_gb_mean, gpu_util_percent_mean, gpu_memory_gb_mean
    )

    # Tokens per hour
    tokens_per_hour = tokens_per_second * 3600

    # Cost per million tokens
    cost_per_million_tokens = (
        (cost_per_hour / tokens_per_hour) * 1_000_000 if tokens_per_hour > 0 else 0.0
    )

    # Tokens per dollar
    tokens_per_dollar = tokens_per_hour / cost_per_hour if cost_per_hour > 0 else 0.0

    # Efficiency metrics
    memory_efficiency = (
        tokens_per_second / memory_mb_mean if memory_mb_mean > 0 else 0.0
    )
    compute_efficiency = (
        tokens_per_second / avg_latency_ms if avg_latency_ms > 0 else 0.0
    )

    return CostProfile(
        backend=backend,
        tokens_per_second=tokens_per_second,
        avg_latency_ms=avg_latency_ms,
        memory_mb_mean=memory_mb_mean,
        memory_mb_peak=memory_mb_peak,
        gpu_util_percent_mean=gpu_util_mean,
        gpu_memory_mb_mean=gpu_memory_mb_mean,
        cost_per_million_tokens_usd=cost_per_million_tokens,
        cost_per_hour_usd=cost_per_hour,
        tokens_per_dollar=tokens_per_dollar,
        memory_efficiency=memory_efficiency,
        compute_efficiency=compute_efficiency,
        n_samples=len(backend_data),
    )


def generate_cost_comparison_table(
    cost_profiles: list[CostProfile],
) -> pd.DataFrame:
    """Generate cost comparison table."""
    data = []

    for profile in cost_profiles:
        data.append(
            {
                "backend": profile.backend,
                "tokens/s": f"{profile.tokens_per_second:.1f}",
                "avg_latency_ms": f"{profile.avg_latency_ms:.1f}",
                "$/1M tokens": f"${profile.cost_per_million_tokens_usd:.4f}",
                "$/hour": f"${profile.cost_per_hour_usd:.4f}",
                "tokens/$": f"{profile.tokens_per_dollar:.0f}",
                "memory_mb": f"{profile.memory_mb_mean:.0f}",
                "gpu_util_%": (
                    f"{profile.gpu_util_percent_mean:.1f}"
                    if profile.gpu_util_percent_mean
                    else "N/A"
                ),
                "samples": profile.n_samples,
            }
        )

    return pd.DataFrame(data)


def save_cost_analysis(
    cost_profiles: list[CostProfile],
    output_path: Path,
) -> None:
    """Save cost analysis to JSON."""
    data = {
        "profiles": [
            {
                "backend": p.backend,
                "tokens_per_second": p.tokens_per_second,
                "avg_latency_ms": p.avg_latency_ms,
                "memory_mb_mean": p.memory_mb_mean,
                "memory_mb_peak": p.memory_mb_peak,
                "gpu_util_percent_mean": p.gpu_util_percent_mean,
                "gpu_memory_mb_mean": p.gpu_memory_mb_mean,
                "cost_per_million_tokens_usd": p.cost_per_million_tokens_usd,
                "cost_per_hour_usd": p.cost_per_hour_usd,
                "tokens_per_dollar": p.tokens_per_dollar,
                "memory_efficiency": p.memory_efficiency,
                "compute_efficiency": p.compute_efficiency,
                "n_samples": p.n_samples,
            }
            for p in cost_profiles
        ],
        "pricing_assumptions": PRICING,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def main() -> None:
    """Generate cost analysis from TR117 results."""
    import argparse

    parser = argparse.ArgumentParser(description="TR117 cost analysis")
    parser.add_argument(
        "--metrics",
        type=Path,
        default=Path("results/tr117/metrics.csv"),
        help="Path to metrics CSV",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/tr117/cost_analysis.json"),
        help="Output path",
    )

    args = parser.parse_args()

    # Load metrics
    df = pd.read_csv(args.metrics)

    # Compute cost profiles
    backends = df["backend"].unique()
    cost_profiles = [compute_cost_profile(backend, df) for backend in backends]

    # Generate comparison table
    table = generate_cost_comparison_table(cost_profiles)
    print("\nCost Comparison:")
    print(table.to_string(index=False))

    # Save analysis
    save_cost_analysis(cost_profiles, args.output)
    print(f"\nCost analysis saved to: {args.output}")


if __name__ == "__main__":
    main()
