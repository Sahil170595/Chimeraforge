"""Benchmark metrics — dataclasses and statistical helpers.

Defines the core data model for benchmark results: individual run
metrics, statistical summaries, environment metadata, and the
top-level BenchmarkResult container.
"""

from __future__ import annotations

import json
import platform
import statistics
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


@dataclass
class RunMetrics:
    """Metrics from a single inference call."""

    tokens_generated: int
    throughput_tps: float
    ttft_ms: float
    total_duration_ms: float
    prompt_eval_duration_ms: float
    eval_duration_ms: float


@dataclass
class StatSummary:
    """Percentile-based statistical summary."""

    mean: float
    p50: float
    p95: float
    p99: float
    min: float
    max: float
    stddev: float


@dataclass
class AggregateMetrics:
    """Statistical summary across multiple runs."""

    count: int
    throughput_tps: StatSummary
    ttft_ms: StatSummary
    total_duration_ms: StatSummary
    tokens_generated: int


@dataclass
class EnvironmentInfo:
    """Reproducibility metadata captured at benchmark start."""

    os: str
    platform: str
    python_version: str
    chimeraforge_version: str
    gpu_name: str | None
    gpu_driver: str | None
    cuda_version: str | None
    backend_name: str
    backend_version: str | None


@dataclass
class BenchmarkResult:
    """Complete result from one benchmark configuration."""

    model: str
    backend: str
    quant: str | None
    workload: str
    runs: int
    context_length: int
    individual_runs: list[RunMetrics]
    aggregate: AggregateMetrics
    environment: EnvironmentInfo
    timestamp: str
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _percentile(sorted_values: list[float], pct: float) -> float:
    """Linearly interpolated percentile on pre-sorted values."""
    if not sorted_values:
        return 0.0
    k = (len(sorted_values) - 1) * pct
    f = int(k)
    c = min(f + 1, len(sorted_values) - 1)
    if f == c:
        return sorted_values[f]
    return sorted_values[f] * (c - k) + sorted_values[c] * (k - f)


def summarize(values: list[float]) -> StatSummary:
    """Compute statistical summary from a list of values."""
    if not values:
        return StatSummary(
            mean=0.0,
            p50=0.0,
            p95=0.0,
            p99=0.0,
            min=0.0,
            max=0.0,
            stddev=0.0,
        )
    s = sorted(values)
    sd = statistics.stdev(values) if len(values) > 1 else 0.0
    return StatSummary(
        mean=statistics.mean(values),
        p50=_percentile(s, 0.50),
        p95=_percentile(s, 0.95),
        p99=_percentile(s, 0.99),
        min=s[0],
        max=s[-1],
        stddev=sd,
    )


def aggregate_runs(runs: list[RunMetrics]) -> AggregateMetrics:
    """Aggregate a list of RunMetrics into an AggregateMetrics."""
    return AggregateMetrics(
        count=len(runs),
        throughput_tps=summarize([r.throughput_tps for r in runs]),
        ttft_ms=summarize([r.ttft_ms for r in runs]),
        total_duration_ms=summarize([r.total_duration_ms for r in runs]),
        tokens_generated=sum(r.tokens_generated for r in runs),
    )


def collect_environment(
    backend_name: str,
    backend_version: str | None = None,
) -> EnvironmentInfo:
    """Collect environment metadata for reproducibility."""
    import chimeraforge

    gpu_name: str | None = None
    gpu_driver: str | None = None
    cuda_version: str | None = None
    try:
        import pynvml  # type: ignore[import-untyped]

        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        gpu_name = pynvml.nvmlDeviceGetName(handle)
        if isinstance(gpu_name, bytes):
            gpu_name = gpu_name.decode()
        gpu_driver = pynvml.nvmlSystemGetDriverVersion()
        if isinstance(gpu_driver, bytes):
            gpu_driver = gpu_driver.decode()
        cuda_version = pynvml.nvmlSystemGetCudaDriverVersion_v2()
        cuda_version = f"{cuda_version // 1000}.{(cuda_version % 1000) // 10}"
        pynvml.nvmlShutdown()
    except Exception:
        pass

    return EnvironmentInfo(
        os=platform.system(),
        platform=platform.platform(),
        python_version=platform.python_version(),
        chimeraforge_version=chimeraforge.__version__,
        gpu_name=gpu_name,
        gpu_driver=gpu_driver,
        cuda_version=cuda_version,
        backend_name=backend_name,
        backend_version=backend_version,
    )


def result_to_dict(result: BenchmarkResult) -> dict:
    """Convert a BenchmarkResult to a JSON-serializable dict."""
    return asdict(result)


def result_to_json(result: BenchmarkResult, indent: int = 2) -> str:
    """Serialize a BenchmarkResult to a JSON string."""
    return json.dumps(result_to_dict(result), indent=indent)


def now_iso() -> str:
    """Return current UTC timestamp as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()
