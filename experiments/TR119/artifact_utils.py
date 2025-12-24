"""TR119 artifact utilities (reuses TR118's resolve_repo_path pattern)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

# Reuse TR118's artifact_utils for path resolution
# TR119 doesn't need ONNX/TRT inspection, but we keep the same pattern
try:
    from scripts.tr118.artifact_utils import (
        file_sha256,
        human_bytes,
        resolve_repo_path,
        safe_div,
    )
except ImportError:
    # Fallback if TR118 not available
    def resolve_repo_path(repo_root: Path, path_value: str | Path) -> Path:
        p = Path(path_value)
        if p.is_absolute():
            return p
        return (repo_root / p).resolve()

    def file_sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
        import hashlib
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                h.update(chunk)
        return h.hexdigest()

    def human_bytes(n: int | float | None) -> str:
        if n is None:
            return "N/A"
        n = float(n)
        if n < 0:
            return "N/A"
        units = ["B", "KB", "MB", "GB", "TB"]
        idx = 0
        while n >= 1024 and idx < len(units) - 1:
            n /= 1024.0
            idx += 1
        if idx == 0:
            return f"{int(n)} {units[idx]}"
        return f"{n:.2f} {units[idx]}"

    def safe_div(a: float, b: float) -> float | None:
        import math
        if b == 0:
            return None
        if not math.isfinite(a) or not math.isfinite(b):
            return None
        return float(a / b)


def compute_cost_per_1m_tokens(
    gpu_hours_per_1m_tokens: float,
    on_demand_usd_per_hour: float,
    energy_kwh_per_1m_tokens: float | None = None,
    usd_per_kwh: float | None = None,
) -> dict[str, Any]:
    """
    Compute total cost per 1M tokens.

    Returns:
        {
            "infra_cost_usd_per_1m_tokens": float,
            "energy_cost_usd_per_1m_tokens": float | None,
            "total_cost_usd_per_1m_tokens": float,
        }
    """
    infra_cost = gpu_hours_per_1m_tokens * on_demand_usd_per_hour
    energy_cost = None
    if energy_kwh_per_1m_tokens is not None and usd_per_kwh is not None:
        energy_cost = energy_kwh_per_1m_tokens * usd_per_kwh
    total_cost = infra_cost + (energy_cost or 0.0)
    return {
        "infra_cost_usd_per_1m_tokens": infra_cost,
        "energy_cost_usd_per_1m_tokens": energy_cost,
        "total_cost_usd_per_1m_tokens": total_cost,
    }


def compute_energy_from_power(
    power_watts: float,
    duration_seconds: float,
) -> float:
    """Convert power (W) * duration (s) to energy (Joules)."""
    return power_watts * duration_seconds


def compute_kwh_from_joules(joules: float) -> float:
    """Convert Joules to kWh."""
    # 1 kWh = 3.6e6 J
    return joules / 3.6e6


def compute_carbon_footprint(
    energy_kwh: float,
    carbon_intensity_gco2e_per_kwh: float = 500.0,  # Default: 500 gCO2e/kWh (US grid average)
) -> float:
    """
    Compute carbon footprint in gCO2e from energy consumption.

    Args:
        energy_kwh: Energy consumption in kWh
        carbon_intensity_gco2e_per_kwh: Carbon intensity in gCO2e/kWh
            - US grid average: ~500 gCO2e/kWh
            - EU average: ~300 gCO2e/kWh
            - Renewable: ~50 gCO2e/kWh

    Returns:
        Carbon footprint in gCO2e (grams CO2 equivalent)
    """
    return energy_kwh * carbon_intensity_gco2e_per_kwh


def compute_tco(
    infra_cost_per_1m: float,
    energy_cost_per_1m: float,
    tokens_per_month: float,
    months: int = 12,
    upfront_cost: float = 0.0,
) -> dict[str, Any]:
    """
    Compute Total Cost of Ownership (TCO) over a time period.

    Args:
        infra_cost_per_1m: Infrastructure cost per 1M tokens (USD)
        energy_cost_per_1m: Energy cost per 1M tokens (USD)
        tokens_per_month: Expected token volume per month
        months: Number of months to compute TCO for
        upfront_cost: One-time upfront cost (e.g., hardware purchase)

    Returns:
        {
            "total_cost_usd": float,
            "infra_cost_usd": float,
            "energy_cost_usd": float,
            "upfront_cost_usd": float,
            "cost_per_month_usd": float,
            "cost_per_1m_tokens_usd": float,
        }
    """
    cost_per_1m = infra_cost_per_1m + energy_cost_per_1m
    cost_per_month = (cost_per_1m / 1_000_000.0) * tokens_per_month
    total_cost = upfront_cost + (cost_per_month * months)
    
    return {
        "total_cost_usd": total_cost,
        "infra_cost_usd": (infra_cost_per_1m / 1_000_000.0) * tokens_per_month * months,
        "energy_cost_usd": (energy_cost_per_1m / 1_000_000.0) * tokens_per_month * months,
        "upfront_cost_usd": upfront_cost,
        "cost_per_month_usd": cost_per_month,
        "cost_per_1m_tokens_usd": cost_per_1m,
    }


def compute_roi_savings(
    baseline_cost_per_1m: float,
    alternative_cost_per_1m: float,
    tokens_per_month: float,
    months: int = 12,
) -> dict[str, Any]:
    """
    Compute ROI savings from switching to an alternative pricing tier/backend.

    Args:
        baseline_cost_per_1m: Baseline cost per 1M tokens (USD)
        alternative_cost_per_1m: Alternative cost per 1M tokens (USD)
        tokens_per_month: Expected token volume per month
        months: Number of months

    Returns:
        {
            "savings_usd": float,
            "savings_pct": float,
            "baseline_total_usd": float,
            "alternative_total_usd": float,
        }
    """
    baseline_total = (baseline_cost_per_1m / 1_000_000.0) * tokens_per_month * months
    alternative_total = (alternative_cost_per_1m / 1_000_000.0) * tokens_per_month * months
    savings = baseline_total - alternative_total
    savings_pct = (savings / baseline_total * 100) if baseline_total > 0 else 0.0
    
    return {
        "savings_usd": savings,
        "savings_pct": savings_pct,
        "baseline_total_usd": baseline_total,
        "alternative_total_usd": alternative_total,
    }


def compute_break_even_months(
    upfront_cost: float,
    cost_per_month: float,
) -> float | None:
    """
    Compute break-even point (in months) for upfront investment.

    Args:
        upfront_cost: One-time upfront cost (USD)
        cost_per_month: Monthly operational cost (USD)

    Returns:
        Number of months to break even, or None if never breaks even
    """
    if cost_per_month <= 0:
        return None
    if upfront_cost <= 0:
        return 0.0
    return upfront_cost / cost_per_month


def compute_energy_efficiency_score(
    throughput_tok_s: float,
    power_watts: float,
) -> float:
    """
    Compute energy efficiency score (tokens per Joule).

    Higher is better: more tokens processed per unit of energy.

    Args:
        throughput_tok_s: Throughput in tokens per second
        power_watts: Power consumption in watts

    Returns:
        Energy efficiency score (tokens per Joule)
    """
    if power_watts <= 0:
        return 0.0
    # tokens/J = (tokens/s) / (J/s) = (tokens/s) / watts
    return throughput_tok_s / power_watts

