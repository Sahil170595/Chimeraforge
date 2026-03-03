"""ChimeraForge Benchmarking Engine — run real LLM inference benchmarks.

Public API:
    run_benchmark       Run a single benchmark configuration
    run_quant_sweep     Sweep across quantization levels
    run_context_sweep   Sweep across context lengths
    save_results        Persist results as JSON
    BenchmarkResult     Top-level result container
    RunMetrics          Per-run timing metrics
    AggregateMetrics    Statistical summary
    get_backend         Instantiate a backend adapter
"""

from chimeraforge.bench.backends import get_backend
from chimeraforge.bench.metrics import (
    AggregateMetrics,
    BenchmarkResult,
    EnvironmentInfo,
    RunMetrics,
    StatSummary,
)
from chimeraforge.bench.profiles import WorkloadProfile, get_profile
from chimeraforge.bench.runner import (
    run_benchmark,
    run_context_sweep,
    run_quant_sweep,
    save_results,
)

__all__ = [
    "AggregateMetrics",
    "BenchmarkResult",
    "EnvironmentInfo",
    "RunMetrics",
    "StatSummary",
    "WorkloadProfile",
    "get_backend",
    "get_profile",
    "run_benchmark",
    "run_context_sweep",
    "run_quant_sweep",
    "save_results",
]
