"""Bounded SLO observation from model-selected, two-scrape histogram windows."""

from __future__ import annotations

import math
import re
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit, urlunsplit

from chimeraforge.workload import ENGINE_METRICS, parse_prometheus

PERCENTILE_NUMERATOR = 95
PERCENTILE_DENOMINATOR = 100
PERCENTILE = PERCENTILE_NUMERATOR / PERCENTILE_DENOMINATOR
MILLISECONDS_PER_SECOND = 1000.0
DEFAULT_INTERVAL_SECONDS = 30.0
DEFAULT_TIMEOUT_SECONDS = 10.0
MAX_WINDOWS = 10000
MAX_METRICS_BYTES = 2 * 1024 * 1024
SUM_RELATIVE_TOLERANCE = 1e-7  # Allow floating accumulation error, not contradictory buckets.
SCHEMA_VERSION = 1
METRIC_SOURCES = {
    "vllm": "https://github.com/vllm-project/vllm/blob/v0.30.0/vllm/v1/metrics/loggers.py",
    "sglang": "https://github.com/sgl-project/sglang/blob/v0.5.20/"
    "python/sglang/srt/observability/metrics_collector.py",
}
_SAMPLE = re.compile(
    r"^(?P<name>[a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{(?P<labels>.*)\})?"
    r"\s+(?P<value>\S+)(?:\s+[-+]?\d+(?:\.\d+)?)?$"
)
_LABEL = re.compile(r'\s*([a-zA-Z_][a-zA-Z0-9_]*)="((?:\\[\\n"]|[^"\\])*)"\s*')
_ESCAPE = re.compile(r'\\([\\n"])')


class MonitorError(ValueError):
    """Invalid monitoring input, transport failure, or failed output write."""


class _Unknown(ValueError):
    """A scrape cannot establish the requested SLO."""


def _positive(value: float, name: str) -> None:
    try:
        valid = type(value) in (int, float) and math.isfinite(value) and value > 0
    except OverflowError:
        valid = False
    if not valid:
        raise MonitorError(f"{name} must be a finite positive number")


def _metrics_url(url: str) -> str:
    if not isinstance(url, str):
        raise MonitorError("url must be an HTTP(S) metrics endpoint")
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError as exc:
        raise MonitorError(f"invalid metrics URL: {exc}") from exc
    if (
        parts.scheme not in ("http", "https")
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
        or parts.query
        or parts.fragment
        or (port is not None and port <= 0)
    ):
        raise MonitorError("url must be HTTP(S), without userinfo, query credentials or fragments")
    path = "/metrics" if parts.path in ("", "/") else parts.path
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


@dataclass(frozen=True)
class MonitorRequest:
    backend: str
    url: str
    model: str
    ttft_slo: float | None = None
    tpot_slo: float | None = None
    interval: float = DEFAULT_INTERVAL_SECONDS
    windows: int = 1
    timeout: float = DEFAULT_TIMEOUT_SECONDS

    def validate(self) -> None:
        if not isinstance(self.backend, str) or self.backend not in METRIC_SOURCES:
            raise MonitorError("backend must be vllm or sglang")
        if not isinstance(self.model, str) or not self.model.strip():
            raise MonitorError("model must be an explicit, non-empty model_name label")
        _metrics_url(self.url)
        for name in ("interval", "timeout"):
            _positive(getattr(self, name), name)
        for name in ("ttft_slo", "tpot_slo"):
            value = getattr(self, name)
            if value is not None:
                _positive(value, name)
        if self.ttft_slo is None and self.tpot_slo is None:
            raise MonitorError("at least one explicit TTFT or TPOT target is required")
        if type(self.windows) is not int or not 1 <= self.windows <= MAX_WINDOWS:
            raise MonitorError(f"windows must be an integer between 1 and {MAX_WINDOWS}")


@dataclass(frozen=True)
class MetricAssessment:
    metric: str | None
    semantics: str
    target_ms: float | None
    samples: int | None = None
    p95_lower_ms: float | None = None
    p95_upper_ms: float | None = None
    outcome: str = "unknown"
    confidence: str = "unknown"
    reason: str = ""
    unit: str = "ms"
    percentile: float = PERCENTILE


@dataclass(frozen=True)
class MonitorWindow:
    backend: str
    model: str
    seconds: float
    observed_at: str
    outcome: str
    metrics: dict[str, MetricAssessment]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class MonitorReport:
    backend: str
    model: str
    outcome: str
    windows: list[MonitorWindow] = field(default_factory=list)
    cancelled: bool = False
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> dict:
        result = asdict(self)
        result["metric_contract_source"] = METRIC_SOURCES[self.backend]
        result["notes"] = [
            "P95 bounds describe observed histogram deltas, not statistical confidence intervals.",
            "Targets are explicit operator policy; this is not a calibrated planner drift test.",
            "The pinned source identifies metric semantics, not the running engine's version.",
        ]
        return result


@dataclass(frozen=True)
class _Histogram:
    edges: tuple[float, ...]
    cumulative: tuple[int, ...]
    count: int
    total: float


def _labels(raw: str) -> dict[str, str]:
    labels: dict[str, str] = {}
    position = 0
    while position < len(raw):
        match = _LABEL.match(raw, position)
        if match is None or match[1] in labels:
            raise _Unknown("malformed or duplicate histogram labels")
        labels[match[1]] = _ESCAPE.sub(lambda m: {"n": "\n", '"': '"', "\\": "\\"}[m[1]], match[2])
        position = match.end()
        if position < len(raw):
            if raw[position] != ",":
                raise _Unknown("malformed histogram label separator")
            position += 1
            if position == len(raw):
                raise _Unknown("trailing histogram label separator")
    return labels


def _samples(text: str, names: tuple[str, ...]) -> dict[str, list[tuple[dict, float]]]:
    if len(text.encode("utf-8")) > MAX_METRICS_BYTES:
        raise _Unknown("metrics response exceeds the monitoring size limit")
    result: dict[str, list[tuple[dict, float]]] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name = re.split(r"[\s{]", line, maxsplit=1)[0]
        if name != "process_start_time_seconds" and not any(
            name == base or name.startswith(base + "_") for base in names
        ):
            continue
        match = _SAMPLE.fullmatch(line)
        if match is None:
            raise _Unknown(f"malformed sample for {name}")
        # Keep the existing exposition value parser; decode labels before grouping
        # because commas and escaped quotes are legal inside Prometheus labels.
        parsed = parse_prometheus(f"{match['name']} {match['value']}")
        if not parsed:
            raise _Unknown(f"invalid sample value for {name}")
        value = parsed[name][0][1]
        result.setdefault(name, []).append((_labels(match["labels"] or ""), value))
    return result


def _count(value: float) -> int:
    if not math.isfinite(value) or value < 0 or not value.is_integer():
        raise _Unknown("histogram counts must be finite non-negative integers")
    return int(value)


def _histograms(samples: dict, base: str, model: str) -> dict[tuple, _Histogram]:
    groups: dict[tuple, dict] = {}
    for suffix in ("_bucket", "_count", "_sum"):
        for labels, value in samples.get(base + suffix, []):
            if "model_name" not in labels:
                raise _Unknown(f"{base} has an ambiguous series without model_name")
            if labels["model_name"] != model:
                continue
            key = tuple(sorted((k, v) for k, v in labels.items() if k != "le"))
            group = groups.setdefault(key, {"buckets": {}})
            if suffix == "_bucket":
                try:
                    edge = float(labels["le"])
                except (KeyError, ValueError) as exc:
                    raise _Unknown(f"{base} has an invalid bucket boundary") from exc
                if math.isnan(edge) or edge < 0 or edge in group["buckets"]:
                    raise _Unknown(f"{base} has an invalid or duplicate bucket boundary")
                if math.isfinite(edge) and not math.isfinite(edge * MILLISECONDS_PER_SECOND):
                    raise _Unknown(f"{base} bucket boundary cannot be represented in milliseconds")
                group["buckets"][edge] = _count(value)
            else:
                if "le" in labels or suffix in group:
                    raise _Unknown(f"{base} has duplicate or inconsistent histogram series")
                group[suffix] = value
    if not groups:
        raise _Unknown(f"{base} is missing for the selected model")
    result = {}
    for key, group in groups.items():
        if "_count" not in group or "_sum" not in group:
            raise _Unknown(f"{base} is missing count or sum")
        count = _count(group["_count"])
        total = group["_sum"]
        if not math.isfinite(total) or total < 0:
            raise _Unknown(f"{base} has a non-finite or negative sum")
        edges = tuple(sorted(group["buckets"]))
        values = tuple(group["buckets"][edge] for edge in edges)
        if len(edges) < 2 or edges[-1] != math.inf or values[-1] != count:
            raise _Unknown(f"{base} is missing buckets or its +Inf bucket disagrees with count")
        if any(a > b for a, b in zip(values, values[1:])):
            raise _Unknown(f"{base} has non-monotone cumulative buckets")
        result[key] = _Histogram(edges, values, count, total)
        _check_sum(result[key], base)
    return result


def _check_sum(histogram: _Histogram, base: str) -> None:
    lower, upper, previous_count, previous_edge = 0.0, 0.0, 0, 0.0
    for edge, cumulative in zip(histogram.edges, histogram.cumulative):
        n = cumulative - previous_count
        lower += n * previous_edge
        if n:
            upper += n * edge
        previous_count, previous_edge = cumulative, edge
    tolerance = SUM_RELATIVE_TOLERANCE * max(1.0, histogram.total, lower)
    if (
        not math.isfinite(lower)
        or histogram.total + tolerance < lower
        or histogram.total - tolerance > upper
    ):
        raise _Unknown(f"{base} sum contradicts its histogram buckets")


def _global_reset(first: dict, second: dict, model: str) -> str | None:
    starts = [first.get("process_start_time_seconds"), second.get("process_start_time_seconds")]
    if all(starts) and starts[0] != starts[1]:
        return "process start time changed: engine restart invalidates this window"
    for name, rows in second.items():
        if not name.endswith(("_count", "_bucket", "_sum", "_total", "_created")):
            continue
        for scrape in (first, second):
            for labels, value in scrape.get(name, []):
                if labels.get("model_name") == model and (not math.isfinite(value) or value < 0):
                    return f"{name} has a non-finite or negative cumulative value"
        before = {
            tuple(sorted(labels.items())): value
            for labels, value in first.get(name, [])
            if labels.get("model_name") == model
        }
        for labels, value in rows:
            key = tuple(sorted(labels.items()))
            if labels.get("model_name") != model or key not in before:
                continue
            if value < before[key] or (name.endswith("_created") and value != before[key]):
                return f"{name} reset or changed lifetime: window is unknown"
    return None


def _bounds(first: dict, second: dict, base: str, model: str) -> tuple[int, float, float | None]:
    before, after = _histograms(first, base, model), _histograms(second, base, model)
    if before.keys() != after.keys():
        raise _Unknown(f"{base} series changed; a matching t0 baseline is required")
    edges = None
    counts: list[int] = []
    count = 0
    for key, end in after.items():
        start = before[key]
        if start.edges != end.edges or (edges is not None and edges != end.edges):
            raise _Unknown(f"{base} bucket boundaries differ between scrapes or series")
        if edges is None:
            edges, counts = end.edges, [0] * len(end.edges)
        growth = [b - a for a, b in zip(start.cumulative, end.cumulative)]
        n = end.count - start.count
        if n < 0 or any(x < 0 for x in growth) or end.total < start.total:
            raise _Unknown(f"{base} counter reset invalidates this window")
        if any(a > b for a, b in zip(growth, growth[1:])) or growth[-1] != n:
            raise _Unknown(f"{base} has inconsistent histogram deltas")
        if n == 0 and end.total != start.total:
            raise _Unknown(f"{base} sum changed without observations")
        _check_sum(_Histogram(end.edges, tuple(growth), n, end.total - start.total), base)
        counts = [a + b for a, b in zip(counts, growth)]
        count += n
    if count == 0:
        raise _Unknown(f"{base} has no observations in this window")
    rank = (PERCENTILE_NUMERATOR * count + PERCENTILE_DENOMINATOR - 1) // PERCENTILE_DENOMINATOR
    assert edges is not None
    index = next(i for i, n in enumerate(counts) if n >= rank)
    lower = 0.0 if index == 0 else edges[index - 1] * MILLISECONDS_PER_SECOND
    upper = edges[index] * MILLISECONDS_PER_SECOND
    return count, lower, upper if math.isfinite(upper) else None


def _assessment(
    first: dict,
    second: dict,
    base: str | None,
    semantics: str,
    target: float | None,
    model: str,
    invalid: str | None,
) -> MetricAssessment:
    if invalid or base is None:
        reason = invalid or "SGLang's ITL histogram does not expose per-request TPOT"
        return MetricAssessment(base, semantics, target, reason=reason)
    try:
        count, lower, upper = _bounds(first, second, base, model)
    except _Unknown as exc:
        return MetricAssessment(base, semantics, target, reason=str(exc))
    if target is None:
        outcome, reason = "unknown", "informational observation; no target supplied"
    elif upper is not None and upper <= target:
        outcome, reason = "pass", "observed P95 upper bucket bound meets target"
    elif lower >= target:
        outcome, reason = "breach", "observed P95 exceeds the lower bucket boundary at target"
    else:
        outcome, reason = "unknown", "P95 bucket straddles target; finer buckets are required"
    return MetricAssessment(
        base, semantics, target, count, lower, upper, outcome, "histogram-bound", reason
    )


def _outcome(statuses: list[str]) -> str:
    if "breach" in statuses:
        return "breach"
    return "pass" if statuses and all(x == "pass" for x in statuses) else "unknown"


def evaluate_window(
    first: str,
    second: str,
    *,
    backend: str,
    model: str,
    seconds: float,
    ttft_slo: float | None = None,
    tpot_slo: float | None = None,
) -> MonitorWindow:
    """Assess observed P95 bounds; never interpolate inside a histogram bucket."""
    MonitorRequest(
        backend, "http://localhost/metrics", model, ttft_slo, tpot_slo, interval=seconds
    ).validate()
    bases = {
        "ttft": f"{backend}:time_to_first_token_seconds",
        "tpot": "vllm:request_time_per_output_token_seconds" if backend == "vllm" else None,
        "itl": f"{backend}:inter_token_latency_seconds",
    }
    names = tuple(x for x in bases.values() if x) + (ENGINE_METRICS[backend]["requests_total"],)
    invalid = None
    before, after = {}, {}
    try:
        before, after = _samples(first, names), _samples(second, names)
        invalid = _global_reset(before, after, model)
    except _Unknown as exc:
        invalid = str(exc)
    itl_semantics = (
        "stream-event inter-token gap"
        if backend == "vllm"
        else "token-weighted event interval divided by new tokens"
    )
    metrics = {
        "ttft": _assessment(
            before, after, bases["ttft"], "time to first token", ttft_slo, model, invalid
        ),
        "tpot": _assessment(
            before,
            after,
            bases["tpot"],
            "per-request mean output-token time; backend records zero for <=1 output token",
            tpot_slo,
            model,
            invalid,
        ),
        "itl": _assessment(before, after, bases["itl"], itl_semantics, None, model, invalid),
    }
    statuses = [m.outcome for m in metrics.values() if m.target_ms is not None]
    return MonitorWindow(
        backend, model, seconds, datetime.now(timezone.utc).isoformat(), _outcome(statuses), metrics
    )


def _fetch(url: str, timeout: float) -> str:
    import httpx

    deadline = time.monotonic() + timeout
    payload = bytearray()
    try:
        with httpx.stream("GET", url, timeout=timeout) as response:
            response.raise_for_status()
            for chunk in response.iter_bytes():
                if time.monotonic() > deadline:
                    raise MonitorError("metrics request exceeded its total timeout")
                payload.extend(chunk)
                if len(payload) > MAX_METRICS_BYTES:
                    raise MonitorError("metrics response exceeds the monitoring size limit")
    except httpx.HTTPError as exc:
        raise MonitorError(f"could not scrape metrics endpoint: {exc}") from exc
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MonitorError("metrics endpoint did not return UTF-8 text") from exc


def run_monitor(
    request: MonitorRequest,
    *,
    stop_event: threading.Event | None = None,
    on_window: Callable[[MonitorWindow], None] | None = None,
) -> MonitorReport:
    """Observe a finite number of windows in the caller; cancellation cannot pass."""
    request.validate()
    stop = stop_event if stop_event is not None else threading.Event()
    windows: list[MonitorWindow] = []
    cancelled = False
    try:
        if stop.is_set():
            return MonitorReport(request.backend, request.model, "unknown", cancelled=True)
        url = _metrics_url(request.url)
        first = _fetch(url, request.timeout)
        start = time.monotonic()
        for _ in range(request.windows):
            if stop.wait(request.interval):
                cancelled = True
                break
            second = _fetch(url, request.timeout)
            end = time.monotonic()
            if stop.is_set():
                cancelled = True
                break
            result = evaluate_window(
                first,
                second,
                backend=request.backend,
                model=request.model,
                seconds=end - start,
                ttft_slo=request.ttft_slo,
                tpot_slo=request.tpot_slo,
            )
            windows.append(result)
            if on_window:
                on_window(result)
            first, start = second, end
    except KeyboardInterrupt:
        cancelled = True
    statuses = [x.outcome for x in windows] + (["unknown"] if cancelled else [])
    return MonitorReport(request.backend, request.model, _outcome(statuses), windows, cancelled)


def _escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def prometheus_text(report: MonitorReport) -> str:
    """Export aggregate latest-window gauges; unknown values are omitted, not zero."""
    labels = f'backend="{_escape_label(report.backend)}",model="{_escape_label(report.model)}"'
    rows = [
        "# HELP chimeraforge_monitor_outcome Overall outcome of the bounded observation.",
        "# TYPE chimeraforge_monitor_outcome gauge",
    ]
    for outcome in ("pass", "breach", "unknown"):
        rows.append(
            f'chimeraforge_monitor_outcome{{{labels},outcome="{outcome}"}} '
            f"{int(report.outcome == outcome)}"
        )
    if report.windows:
        name = "chimeraforge_monitor_metric_outcome"
        rows.extend([f"# HELP {name} Latest window metric outcome.", f"# TYPE {name} gauge"])
        for metric, result in report.windows[-1].metrics.items():
            for outcome in ("pass", "breach", "unknown"):
                rows.append(
                    f'{name}{{{labels},metric="{metric}",outcome="{outcome}"}} '
                    f"{int(result.outcome == outcome)}"
                )
        for field_name in ("target_ms", "samples", "p95_lower_ms", "p95_upper_ms"):
            name = "chimeraforge_monitor_" + field_name
            rows.extend(
                [
                    f"# HELP {name} Latest window {field_name}; absent when unknown.",
                    f"# TYPE {name} gauge",
                ]
            )
            for metric, result in report.windows[-1].metrics.items():
                value = getattr(result, field_name)
                if value is not None:
                    rows.append(f'{name}{{{labels},metric="{metric}"}} {value:g}')
    return "\n".join(rows) + "\n"


def write_prometheus(report: MonitorReport, path: str | Path) -> None:
    """Atomically replace a textfile collector output with the latest aggregate."""
    from tempfile import NamedTemporaryFile

    target, temp = Path(path), None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=target.parent, delete=False, suffix=".tmp"
        ) as stream:
            temp = Path(stream.name)
            stream.write(prometheus_text(report))
        temp.replace(target)
    except OSError as exc:
        raise MonitorError(f"cannot write Prometheus output to {target}: {exc}") from exc
    finally:
        if temp is not None and temp.exists():
            temp.unlink()
