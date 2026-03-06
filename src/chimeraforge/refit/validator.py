"""Validation suite for fitted_models dicts.

Runs a battery of spot-checks against a fitted_models dict to ensure
internal consistency.  Used after refitting to catch regressions before
the updated coefficients are saved.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rich.console import Console


@dataclass
class SpotCheck:
    """One spot-check validation result."""

    name: str
    description: str
    passed: bool
    expected: str
    actual: str


@dataclass
class ValidationResult:
    """Result of the full validation suite."""

    passed: bool
    checks: list[SpotCheck] = field(default_factory=list)
    n_passed: int = 0
    n_failed: int = 0


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def _check_throughput_positive(fitted: dict) -> SpotCheck:
    """All throughput lookup values must be > 0."""
    lookup = fitted.get("throughput", {}).get("lookup", {})
    bad = {k: v for k, v in lookup.items() if v <= 0}
    return SpotCheck(
        name="throughput_positive",
        description="All throughput lookup values > 0",
        passed=len(bad) == 0,
        expected="all values > 0",
        actual=f"{len(bad)} non-positive entries" if bad else "all positive",
    )


def _check_quant_multipliers_ordered(fitted: dict) -> SpotCheck:
    """Quant multipliers should increase as precision decreases.

    Expected order: FP16(1.0) <= Q8_0 <= Q6_K <= Q5_K_M <= Q4_K_M <= Q3_K_S <= Q2_K.
    Lower precision = faster = higher multiplier.
    """
    qm = fitted.get("throughput", {}).get("quant_multipliers", {})
    order = ["FP16", "Q8_0", "Q6_K", "Q5_K_M", "Q4_K_M", "Q3_K_S", "Q2_K"]
    present = [q for q in order if q in qm]
    vals = [qm[q] for q in present]
    monotonic = all(a <= b for a, b in zip(vals, vals[1:]))
    return SpotCheck(
        name="quant_multipliers_ordered",
        description="Multipliers non-decreasing: FP16 <= Q8_0 <= ... <= Q2_K",
        passed=monotonic,
        expected="non-decreasing multipliers",
        actual=", ".join(f"{q}={qm[q]:.2f}" for q in present),
    )


def _check_service_times_positive(fitted: dict) -> SpotCheck:
    """All service times must be > 0."""
    st = fitted.get("latency", {}).get("service_times", {})
    bad = {k: v for k, v in st.items() if v <= 0}
    return SpotCheck(
        name="service_times_positive",
        description="All latency service times > 0",
        passed=len(bad) == 0,
        expected="all values > 0",
        actual=f"{len(bad)} non-positive entries" if bad else "all positive",
    )


def _check_power_law_reasonable(fitted: dict) -> SpotCheck:
    """Power law params: a > 0 and 0 < b < 5."""
    tp = fitted.get("throughput", {})
    a = tp.get("size_power_a", 0)
    b = tp.get("size_power_b", 0)
    ok = a > 0 and 0 < b < 5
    return SpotCheck(
        name="power_law_reasonable",
        description="size_power_a > 0, 0 < size_power_b < 5",
        passed=ok,
        expected="a > 0, 0 < b < 5",
        actual=f"a={a:.4f}, b={b:.4f}",
    )


def _check_safety_factor_range(fitted: dict) -> SpotCheck:
    """Latency safety_factor in [0.5, 1.0]."""
    sf = fitted.get("latency", {}).get("safety_factor", 0.7)
    ok = 0.5 <= sf <= 1.0
    return SpotCheck(
        name="safety_factor_range",
        description="latency safety_factor in [0.5, 1.0]",
        passed=ok,
        expected="0.5 <= safety_factor <= 1.0",
        actual=f"safety_factor={sf}",
    )


def _check_vram_overhead_range(fitted: dict) -> SpotCheck:
    """VRAM overhead_factor in [1.0, 2.0]."""
    of = fitted.get("vram", {}).get("overhead_factor", 1.1)
    ok = 1.0 <= of <= 2.0
    return SpotCheck(
        name="vram_overhead_range",
        description="vram overhead_factor in [1.0, 2.0]",
        passed=ok,
        expected="1.0 <= overhead_factor <= 2.0",
        actual=f"overhead_factor={of:.4f}",
    )


def _check_fp16_fastest(fitted: dict) -> SpotCheck:
    """For each quant level, multiplier >= FP16 (1.0).

    Quantized models should be at least as fast as FP16 (multiplier >= 1.0).
    """
    qm = fitted.get("throughput", {}).get("quant_multipliers", {})
    fp16_val = qm.get("FP16", 1.0)
    bad = {q: v for q, v in qm.items() if q != "FP16" and v < fp16_val}
    return SpotCheck(
        name="fp16_fastest",
        description="All quant multipliers >= FP16 (quantized is faster)",
        passed=len(bad) == 0,
        expected="all quant multipliers >= 1.0",
        actual=f"{len(bad)} violations" if bad else "all >= FP16",
    )


def _check_throughput_not_empty(fitted: dict) -> SpotCheck:
    """At least 1 entry in throughput lookup."""
    lookup = fitted.get("throughput", {}).get("lookup", {})
    ok = len(lookup) >= 1
    return SpotCheck(
        name="throughput_not_empty",
        description="At least 1 entry in throughput lookup",
        passed=ok,
        expected=">= 1 entry",
        actual=f"{len(lookup)} entries",
    )


def _check_quant_fp16_is_one(fitted: dict) -> SpotCheck:
    """quant_multipliers['FP16'] must equal 1.0."""
    qm = fitted.get("throughput", {}).get("quant_multipliers", {})
    fp16 = qm.get("FP16")
    ok = fp16 == 1.0
    return SpotCheck(
        name="quant_fp16_is_one",
        description="quant_multipliers['FP16'] == 1.0",
        passed=ok,
        expected="FP16 = 1.0",
        actual=f"FP16 = {fp16}" if fp16 is not None else "FP16 missing",
    )


def _check_latency_has_entries(fitted: dict) -> SpotCheck:
    """At least 1 entry in service_times."""
    st = fitted.get("latency", {}).get("service_times", {})
    ok = len(st) >= 1
    return SpotCheck(
        name="latency_has_entries",
        description="At least 1 entry in service_times",
        passed=ok,
        expected=">= 1 entry",
        actual=f"{len(st)} entries",
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_ALL_CHECKS = [
    _check_throughput_positive,
    _check_quant_multipliers_ordered,
    _check_service_times_positive,
    _check_power_law_reasonable,
    _check_safety_factor_range,
    _check_vram_overhead_range,
    _check_fp16_fastest,
    _check_throughput_not_empty,
    _check_quant_fp16_is_one,
    _check_latency_has_entries,
]


def validate_fitted_models(fitted: dict) -> ValidationResult:
    """Run the full validation suite against a fitted_models dict.

    Args:
        fitted: A fitted_models dict (same structure as fitted_models.json).

    Returns:
        ValidationResult with per-check pass/fail details.
    """
    checks = [check_fn(fitted) for check_fn in _ALL_CHECKS]
    n_passed = sum(1 for c in checks if c.passed)
    n_failed = len(checks) - n_passed
    return ValidationResult(
        passed=n_failed == 0,
        checks=checks,
        n_passed=n_passed,
        n_failed=n_failed,
    )


def format_validation_table(result: ValidationResult, console: Console) -> None:
    """Print a Rich table showing pass/fail for each check.

    Args:
        result: The ValidationResult to display.
        console: A ``rich.console.Console`` instance.
    """
    from rich.table import Table

    table = Table(title="Validation Results", border_style="blue")
    table.add_column("Check", style="bold")
    table.add_column("Status")
    table.add_column("Expected")
    table.add_column("Actual")

    for c in result.checks:
        status = "[green]PASS[/]" if c.passed else "[red]FAIL[/]"
        table.add_row(c.name, status, c.expected, c.actual)

    console.print(table)

    summary_style = "green" if result.passed else "red"
    console.print(
        f"[{summary_style}]{result.n_passed}/{result.n_passed + result.n_failed} "
        f"checks passed[/{summary_style}]"
    )


def format_validation_json(result: ValidationResult) -> str:
    """Serialize validation results to JSON.

    Args:
        result: The ValidationResult to serialize.

    Returns:
        JSON string with indentation.
    """
    data = {
        "passed": result.passed,
        "n_passed": result.n_passed,
        "n_failed": result.n_failed,
        "checks": [
            {
                "name": c.name,
                "description": c.description,
                "passed": c.passed,
                "expected": c.expected,
                "actual": c.actual,
            }
            for c in result.checks
        ],
    }
    return json.dumps(data, indent=2)
