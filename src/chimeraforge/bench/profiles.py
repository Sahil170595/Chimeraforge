"""Workload profiles for benchmark execution.

Defines three workload patterns that mirror real deployment scenarios:
single (sequential), batch (concurrent burst), and server (Poisson arrivals).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class WorkloadProfile:
    """Benchmark workload configuration."""

    name: str
    concurrency: int
    total_requests: int
    arrival_rate: float | None  # req/s for server mode (Poisson)


PROFILES: dict[str, WorkloadProfile] = {
    "single": WorkloadProfile("single", concurrency=1, total_requests=5, arrival_rate=None),
    "batch": WorkloadProfile("batch", concurrency=4, total_requests=20, arrival_rate=None),
    "server": WorkloadProfile("server", concurrency=8, total_requests=40, arrival_rate=2.0),
}


def get_profile(
    name: str,
    rate: float | None = None,
    runs: int | None = None,
) -> WorkloadProfile:
    """Get a workload profile, optionally overriding rate or total_requests.

    Args:
        name: Profile name ("single", "batch", or "server").
        rate: Override arrival_rate for server profile.
        runs: Override total_requests.

    Returns:
        A WorkloadProfile with any overrides applied.

    Raises:
        ValueError: If profile name is unknown.
    """
    if name not in PROFILES:
        raise ValueError(f"Unknown profile: {name}. Available: {list(PROFILES)}")
    base = PROFILES[name]
    return WorkloadProfile(
        name=base.name,
        concurrency=base.concurrency,
        total_requests=runs if runs is not None else base.total_requests,
        arrival_rate=rate if rate is not None else base.arrival_rate,
    )
